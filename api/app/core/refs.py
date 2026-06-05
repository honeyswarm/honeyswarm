"""Helpers for working with Beanie Links.

A Link field may hold either an unresolved link (with ``.ref.id``) when loaded
from the DB, or the full Document (with ``.id``) when just assigned in memory.
``link_id`` returns the string id for both cases.
"""
from typing import Any, Optional


def link_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    ref = getattr(value, "ref", None)
    if ref is not None:
        return str(ref.id)
    doc_id = getattr(value, "id", None)
    return str(doc_id) if doc_id is not None else None
