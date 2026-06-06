"""Per-honeypot event normalizers.

Ported from the channel-based ``normalise()`` in the old broker
(honeyswarm_broker/file-system/usr/bin/subscriber.py). Previously keyed off
HPFeeds channels; now keyed off a ``normalizer`` name carried in the agent's
MQTT event envelope (selected by each honeypot's manifest ``log.normalizer``).

A normalizer takes the honeypot's raw JSON event and returns the canonical
fields ``service``, ``port``, ``source_ip``, ``honeypot_type``. Anything not
recognised falls through ``generic`` which copies through any pre-set fields.

``generic`` also accepts a per-honeypot ``field_map`` and ``static`` (defined in
the manifest's ``log:`` section and carried in the event envelope), so a custom
honeypot can map its own JSON keys onto the canonical fields without any code:

    log:
      normalizer: generic
      static:            # literal canonical values
        service: Redis
        honeypot_type: MyRedis
      field_map:         # canonical field <- payload key path (dot-notation)
        source_ip: event.client.ip
        port: dst_port

A normalizer may return ``None`` to signal "this log line is not an event worth
storing" (e.g. a honeypot that logs its own framework/startup output as JSON);
ingest drops those instead of inserting a hollow event.
"""
from typing import Any, Callable, Optional

CanonicalEvent = dict[str, Any]

_CANON_FIELDS = ("service", "port", "source_ip", "honeypot_type")


def _base() -> CanonicalEvent:
    return {
        "service": "Unknown",
        "port": 0,
        "source_ip": "",
        "honeypot_type": "Generic",
    }


def _dig(payload: dict[str, Any], path: Any) -> Any:
    """Look up a dot-notation key path in a (possibly nested) payload dict."""
    cur: Any = payload
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def generic(
    payload: dict[str, Any],
    field_map: Optional[dict[str, Any]] = None,
    static: Optional[dict[str, Any]] = None,
) -> CanonicalEvent:
    event = _base()
    # Precedence (low -> high): base < static literals < canonical keys in the
    # payload < explicit field_map lookups.
    if isinstance(static, dict):
        for field in _CANON_FIELDS:
            if field in static:
                event[field] = static[field]
    for field in _CANON_FIELDS:
        if field in payload:
            event[field] = payload[field]
    if isinstance(field_map, dict):
        for field, key_path in field_map.items():
            if field not in _CANON_FIELDS:
                continue
            value = _dig(payload, key_path)
            if value is not None:
                event[field] = value
    # port must be an int for OpenSearch aggregations/sort.
    try:
        event["port"] = int(event["port"])
    except (TypeError, ValueError):
        event["port"] = 0
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
    # GoSecure PyRDP's mitm.json uses ``clientIp``; keep the legacy keys as a
    # fallback for older payloads.
    event["source_ip"] = (
        payload.get("clientIp")
        or payload.get("source_ip")
        or payload.get("src_ip", "")
    )
    return event


# Conpot's default template maps a data_type to a human service name.
_CONPOT_SERVICES = {
    "modbus": "Modbus",
    "s7comm": "S7comm",
    "snmp": "SNMP",
    "http": "HTTP",
    "ipmi": "IPMI",
    "enip": "EtherNet/IP",
    "bacnet": "BACnet",
    "ftp": "FTP",
    "tftp": "TFTP",
}


def conpot(payload: dict[str, Any]) -> CanonicalEvent:
    event = _base()
    event["honeypot_type"] = "Conpot"
    event["source_ip"] = payload.get("src_ip", "")
    event["port"] = int(payload.get("dst_port") or 0)
    data_type = payload.get("data_type")
    if data_type:
        event["service"] = _CONPOT_SERVICES.get(data_type, str(data_type))
    return event


def http(payload: dict[str, Any]) -> CanonicalEvent:
    # The HTTP honeypot logs one flat JSON object per request, always carrying
    # ``source_ip`` and the ``port`` it was reached on. Every line is a real
    # request, so there is no framework noise to filter.
    event = _base()
    event["honeypot_type"] = "HTTP"
    event["service"] = "HTTP"
    try:
        event["port"] = int(payload.get("port") or 80)
    except (TypeError, ValueError):
        event["port"] = 80
    event["source_ip"] = (
        payload.get("source_ip")
        or payload.get("http_remote")
        or payload.get("src_ip", "")
    )
    return event


def wordpress(payload: dict[str, Any]) -> CanonicalEvent:
    # The high-interaction WordPress honeypot's proxy logs one flat JSON object
    # per request, always carrying ``source_ip`` (plus http_method/http_path/
    # http_post). Every line is a real request, so there is no framework noise
    # to filter.
    event = _base()
    event["honeypot_type"] = "Wordpress"
    event["service"] = "HTTP"
    event["port"] = 80
    event["source_ip"] = (
        payload.get("source_ip")
        or payload.get("http_remote")
        or payload.get("src_ip", "")
    )
    return event


NORMALIZERS: dict[str, Callable[[dict[str, Any]], Optional[CanonicalEvent]]] = {
    "generic": generic,
    "cowrie": cowrie,
    "pyrdp": pyrdp,
    "conpot": conpot,
    "http": http,
    "wordpress": wordpress,
}


def normalize(
    normalizer: str | None,
    payload: dict[str, Any],
    field_map: Optional[dict[str, Any]] = None,
    static: Optional[dict[str, Any]] = None,
) -> Optional[CanonicalEvent]:
    func = NORMALIZERS.get((normalizer or "generic").lower(), generic)
    try:
        # field_map/static only apply to the generic normalizer; the dedicated
        # ones have their own field knowledge.
        if func is generic:
            return generic(payload, field_map=field_map, static=static)
        return func(payload)
    except Exception:  # noqa: BLE001 - never let a bad payload break ingest
        return generic(payload, field_map=field_map, static=static)
