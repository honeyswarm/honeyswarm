"""OpenSearch client + index bootstrap for event search/analytics.

Replaces the EOL Elasticsearch 7.8 client used by the old broker subscriber.
"""
import logging

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


async def close_opensearch() -> None:
    global _client
    if _client is not None:
        logger.info("Closing OpenSearch connection")
        await _client.close()
        _client = None
