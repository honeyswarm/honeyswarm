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

DOCUMENT_MODELS = [
    Config,
    Frame,
    Hive,
    Honeypot,
    HoneypotEvent,
    HoneypotInstance,
    Job,
    Role,
    User,
]

__all__ = ["DOCUMENT_MODELS", *[m.__name__ for m in DOCUMENT_MODELS]]
