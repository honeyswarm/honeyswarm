"""Per-honeypot event normalizers.

Ported from the channel-based ``normalise()`` in the old broker
(honeyswarm_broker/file-system/usr/bin/subscriber.py). Previously keyed off
HPFeeds channels; now keyed off a ``normalizer`` name carried in the agent's
MQTT event envelope (selected by each honeypot's manifest ``log.normalizer``).

A normalizer takes the honeypot's raw JSON event and returns the canonical
fields ``service``, ``port``, ``source_ip``, ``honeypot_type``. Anything not
recognised falls through ``generic`` which copies through any pre-set fields.
"""
from typing import Any, Callable

CanonicalEvent = dict[str, Any]


def _base() -> CanonicalEvent:
    return {
        "service": "Unknown",
        "port": 0,
        "source_ip": "",
        "honeypot_type": "Generic",
    }


def generic(payload: dict[str, Any]) -> CanonicalEvent:
    event = _base()
    for field in ("port", "service", "source_ip", "honeypot_type"):
        if field in payload:
            event[field] = payload[field]
    return event


def cowrie(payload: dict[str, Any]) -> CanonicalEvent:
    event = _base()
    event["honeypot_type"] = "Cowrie"
    event["source_ip"] = payload.get("peerIP") or payload.get("src_ip", "")
    if payload.get("protocol") == "telnet":
        event["port"] = 23
        event["service"] = "Telnet"
    else:
        event["port"] = 22
        event["service"] = "SSH"
    return event


def pyrdp(payload: dict[str, Any]) -> CanonicalEvent:
    event = _base()
    event["honeypot_type"] = "PyRDP"
    event["service"] = "RDP"
    event["port"] = 3389
    event["source_ip"] = payload.get("source_ip") or payload.get("src_ip", "")
    return event


def http(payload: dict[str, Any]) -> CanonicalEvent:
    event = _base()
    event["honeypot_type"] = "HTTP"
    event["service"] = "HTTP"
    event["port"] = 80
    event["source_ip"] = payload.get("src_ip") or payload.get("source_ip", "")
    return event


def wordpress(payload: dict[str, Any]) -> CanonicalEvent:
    event = http(payload)
    event["honeypot_type"] = "Wordpress"
    return event


NORMALIZERS: dict[str, Callable[[dict[str, Any]], CanonicalEvent]] = {
    "generic": generic,
    "cowrie": cowrie,
    "pyrdp": pyrdp,
    "http": http,
    "wordpress": wordpress,
}


def normalize(normalizer: str | None, payload: dict[str, Any]) -> CanonicalEvent:
    func = NORMALIZERS.get((normalizer or "generic").lower(), generic)
    try:
        return func(payload)
    except Exception:  # noqa: BLE001 - never let a bad payload break ingest
        return generic(payload)
