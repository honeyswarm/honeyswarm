"""Beanie document definitions.

Ported from honeyswarm/honeyswarm/honeyswarm/models.py.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import pymongo
from beanie import Document, Indexed, Link
from pydantic import Field


def utcnow() -> datetime:
    return datetime.utcnow()


class ConnectionState(str, Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"


class Config(Document):
    """Global configuration singleton (was ``Config``)."""

    honeyswarm_host: Optional[str] = None
    honeyswarm_api: Optional[str] = None
    # broker_host removed (HPFeeds gone); kept loose via Settings/MQTT instead.

    class Settings:
        name = "config"


class HoneypotEvent(Document):
    """Normalized honeypot event (was ``HoneypotEvents``).

    Source of truth for raw events stays in Mongo; OpenSearch holds a copy for
    search/analytics. Collection name preserved (``honeypot_events``).
    """

    date: datetime = Field(default_factory=utcnow)
    service: str = "Unknown"
    port: int = 0
    honeypot_type: str = "Generic"
    source_ip: str = ""
    hive_id: Optional[str] = None
    honeypot_instance_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "honeypot_events"
        indexes = [
            [("date", pymongo.DESCENDING)],
            [("port", pymongo.DESCENDING)],
            [("honeypot_type", pymongo.DESCENDING)],
            [("service", pymongo.DESCENDING)],
            [("source_ip", pymongo.DESCENDING)],
        ]


class Frame(Document):
    """Host base-setup definition (was ``Frame``)."""

    name: Indexed(str, unique=True)
    description: Optional[str] = None
    supported_os: list[str] = Field(default_factory=list)
    manifest: Optional[str] = None  # replaces frame_state_path
    pillar: list[Any] = Field(default_factory=list)

    class Settings:
        name = "frame"


class Honeypot(Document):
    """Honeypot definition / template (was ``Honeypot``)."""

    name: Indexed(str, unique=True)
    honey_type: Optional[str] = None
    description: Optional[str] = None
    container_name: Optional[str] = None
    manifest: Optional[str] = None  # replaces honeypot_state_file
    normalizer: Optional[str] = None  # replaces hpfeeds channels
    pillar: list[Any] = Field(default_factory=list)
    report_fields: list[str] = Field(default_factory=lambda: ["source_ip"])

    class Settings:
        name = "honeypot"


class HoneypotInstance(Document):
    """A honeypot deployed on a hive (was ``HoneypotInstance``)."""

    honeypot: Optional[Link[Honeypot]] = None
    hive: Optional[Link["Hive"]] = None
    pillar: dict[str, Any] = Field(default_factory=dict)
    status: str = "Pending"

    class Settings:
        name = "honeypot_instance"


class Hive(Document):
    """A host that runs honeypots (was ``Hive``).

    Salt minion fields replaced by agent/MQTT connection state.
    """

    name: Indexed(str, unique=True)
    registered: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    last_seen: Optional[datetime] = None
    grains: dict[str, Any] = Field(
        default_factory=lambda: {"osfullname": "Not Polled", "ipv4": []}
    )
    frame: Optional[Link[Frame]] = None
    event_count: int = 0

    # Agent / MQTT control plane (replaces Salt minion)
    agent_token_hash: Optional[str] = None
    mqtt_username: Optional[str] = None
    agent_version: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    connection_state: ConnectionState = ConnectionState.UNKNOWN

    class Settings:
        name = "hive"


class Job(Document):
    """Async command tracking (was ``PepperJobs``).

    Salt JIDs replaced by agent command ids carried over MQTT.
    """

    command_id: Optional[str] = None  # was job_id
    job_type: Optional[str] = None
    job_short: Optional[str] = None
    job_description: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    last_check: Optional[datetime] = None
    complete: bool = False
    completed_at: Optional[datetime] = None
    job_response: Optional[str] = None
    hive: Optional[Link[Hive]] = None

    class Settings:
        name = "job"


class Role(Document):
    name: Indexed(str, unique=True)
    description: Optional[str] = None

    class Settings:
        name = "role"


class User(Document):
    email: Indexed(str, unique=True)
    password: str
    name: Optional[str] = None
    active: bool = False
    confirmed_at: Optional[datetime] = None
    roles: list[str] = Field(default_factory=list)

    class Settings:
        name = "user"
