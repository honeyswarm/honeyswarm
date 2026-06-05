"""Events API, backed by OpenSearch.

Replaces the old DataTables ``/events/paginate`` endpoint. Preserves the
prefix search syntax from the legacy UI: ``ip:``, ``service:``, ``port:``,
``honeypot:``. A bare term is matched across source_ip/service/honeypot_type.
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Query

from app.core.config import settings
from app.db.opensearch import get_opensearch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])

_PREFIX_FIELDS = {
    "ip": "source_ip",
    "service": "service",
    "port": "port",
    "honeypot": "honeypot_type",
}


def build_query(search: Optional[str]) -> dict[str, Any]:
    if not search:
        return {"match_all": {}}

    prefix, _, value = search.partition(":")
    if value and prefix in _PREFIX_FIELDS:
        field = _PREFIX_FIELDS[prefix]
        if field == "port":
            try:
                return {"term": {"port": int(value)}}
            except ValueError:
                return {"match_none": {}}
        return {"term": {field: value.strip()}}

    return {
        "multi_match": {
            "query": search,
            "fields": ["source_ip", "service", "honeypot_type"],
        }
    }


@router.get("")
async def list_events(
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=500),
) -> dict[str, Any]:
    client = get_opensearch()
    body = {
        "query": build_query(search),
        "sort": [{"date": {"order": "desc"}}],
        "from": (page - 1) * page_size,
        "size": page_size,
    }
    result = await client.search(index=settings.opensearch_event_index, body=body)
    hits = result.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [h["_source"] for h in hits.get("hits", [])],
    }


@router.get("/stats")
async def event_stats() -> dict[str, Any]:
    """Aggregations for dashboard widgets (counts by service / top source IPs)."""
    client = get_opensearch()
    body = {
        "size": 0,
        "aggs": {
            "by_service": {"terms": {"field": "service", "size": 10}},
            "by_honeypot": {"terms": {"field": "honeypot_type", "size": 10}},
            "top_sources": {"terms": {"field": "source_ip", "size": 10}},
        },
    }
    result = await client.search(index=settings.opensearch_event_index, body=body)
    aggs = result.get("aggregations", {})
    total = result.get("hits", {}).get("total", {}).get("value", 0)
    return {
        "total": total,
        "by_service": aggs.get("by_service", {}).get("buckets", []),
        "by_honeypot": aggs.get("by_honeypot", {}).get("buckets", []),
        "top_sources": aggs.get("top_sources", {}).get("buckets", []),
    }
