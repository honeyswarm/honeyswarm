"""OpenSearch client + index bootstrap for event search/analytics.

Replaces the EOL Elasticsearch 7.8 client used by the old broker subscriber.
"""
import asyncio
import logging

import aiohttp
from opensearchpy import AsyncOpenSearch

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenSearch | None = None

EVENT_PROPERTIES = {
    "date": {"type": "date"},
    "service": {"type": "keyword"},
    "port": {"type": "integer"},
    "honeypot_type": {"type": "keyword"},
    "source_ip": {"type": "keyword"},
    "hive_id": {"type": "keyword"},
    "honeypot_instance_id": {"type": "keyword"},
    "payload": {"type": "object", "enabled": True},
}

EVENT_MAPPING = {"mappings": {"properties": EVENT_PROPERTIES}}


def get_opensearch() -> AsyncOpenSearch:
    if _client is None:
        raise RuntimeError("OpenSearch client not initialised")
    return _client


async def init_opensearch() -> AsyncOpenSearch:
    global _client
    logger.info("Connecting to OpenSearch at %s:%s", settings.opensearch_host, settings.opensearch_port)
    _client = AsyncOpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_auth=(settings.opensearch_user, settings.opensearch_password),
        use_ssl=settings.opensearch_use_ssl,
        verify_certs=settings.opensearch_verify_certs,
        ssl_show_warn=False,
    )
    index = settings.opensearch_event_index
    try:
        # Index template ensures the correct field types even if an index is
        # auto-created by the first document (otherwise text fields can't be
        # aggregated/sorted).
        await _client.indices.put_index_template(
            name=f"{index}-template",
            body={
                "index_patterns": [f"{index}*"],
                "template": {"mappings": {"properties": EVENT_PROPERTIES}},
            },
        )
        if not await _client.indices.exists(index=index):
            await _client.indices.create(index=index, body=EVENT_MAPPING)
            logger.info("Created OpenSearch index %s", index)
    except Exception as err:  # noqa: BLE001 - bootstrap should not crash startup
        logger.warning("Could not ensure OpenSearch index/template: %s", err)
    return _client


async def ensure_dashboards_index_pattern() -> None:
    """Create/repair the OpenSearch Dashboards index pattern for events.

    The events index uses a top-level ``date`` field as its timestamp. Without
    an index pattern whose ``timeFieldName`` is ``date``, the Dashboards Discover
    view applies a time filter against a missing field and shows nothing. This
    provisions the pattern (idempotent via ``overwrite=true``) so :5601 works on
    a fresh install. Best-effort: Dashboards may still be booting, so retry a few
    times and never raise.
    """
    index = settings.opensearch_event_index
    url = (
        f"{settings.opensearch_dashboards_url.rstrip('/')}"
        f"/api/saved_objects/index-pattern/{index}?overwrite=true"
    )
    body = {"attributes": {"title": f"{index}*", "timeFieldName": "date"}}
    headers = {"osd-xsrf": "true", "Content-Type": "application/json"}

    for attempt in range(1, 11):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    if resp.status in (200, 201):
                        logger.info("Ensured Dashboards index pattern %s* (time=date)", index)
                        return
                    text = await resp.text()
                    logger.debug("Dashboards index-pattern attempt %s: HTTP %s %s",
                                 attempt, resp.status, text[:200])
        except Exception as err:  # noqa: BLE001 - provisioning must not crash startup
            logger.debug("Dashboards not ready (attempt %s): %s", attempt, err)
        await asyncio.sleep(6)
    logger.warning(
        "Could not provision Dashboards index pattern at %s; set it manually "
        "(time field = 'date') if you use OpenSearch Dashboards.",
        settings.opensearch_dashboards_url,
    )


async def close_opensearch() -> None:
    global _client
    if _client is not None:
        logger.info("Closing OpenSearch connection")
        await _client.close()
        _client = None
