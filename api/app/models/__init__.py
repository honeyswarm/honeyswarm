"""Beanie document models, ported from the old MongoEngine ``models.py``.

Field names and collection names are preserved where practical so existing
Mongo data remains readable. Notable changes vs the old model set:

* ``AuthKey`` and the separate ``hpfeeds_db`` are dropped -- HPFeeds is gone.
* ``PepperJobs`` becomes ``Job`` (Salt JIDs replaced by agent command ids).
* ``Hive`` gains agent/MQTT connection fields (replacing Salt minion state).
* ``Honeypot`` gains a ``manifest`` (replacing the Salt ``honeypot_state_file``)
  and a ``normalizer`` selector (replacing HPFeeds ``channels``).
"""
from .documents import (
    Config,
    Frame,
    Hive,
    Honeypot,
    HoneypotEvent,
    HoneypotInstance,
    Job,
    Role,
    User,
)

# HoneypotEvent is intentionally NOT a Beanie document: honeypot events live
# solely in OpenSearch, not Mongo, so it must not be registered here (that would
# recreate the ``honeypot_events`` collection). It is still imported/exported as
# a plain pydantic model for ingest to shape OpenSearch documents.
DOCUMENT_MODELS = [
    Config,
    Frame,
    Hive,
    Honeypot,
    HoneypotInstance,
    Job,
    Role,
    User,
]

__all__ = ["DOCUMENT_MODELS", "HoneypotEvent", *[m.__name__ for m in DOCUMENT_MODELS]]
