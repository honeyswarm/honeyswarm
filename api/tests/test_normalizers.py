"""Unit tests for the ported event normalizers (was subscriber.normalise)."""
from app.services.normalizers import normalize


def test_cowrie_ssh():
    event = normalize("cowrie", {"peerIP": "203.0.113.7", "protocol": "ssh"})
    assert event["source_ip"] == "203.0.113.7"
    assert event["service"] == "SSH"
    assert event["port"] == 22
    assert event["honeypot_type"] == "Cowrie"


def test_cowrie_telnet():
    event = normalize("cowrie", {"peerIP": "203.0.113.7", "protocol": "telnet"})
    assert event["service"] == "Telnet"
    assert event["port"] == 23


def test_pyrdp():
    event = normalize("pyrdp", {"source_ip": "198.51.100.23"})
    assert event["port"] == 3389
    assert event["service"] == "RDP"


def test_pyrdp_clientip_key():
    event = normalize("pyrdp", {"clientIp": "198.51.100.9"})
    assert event["source_ip"] == "198.51.100.9"
    assert event["honeypot_type"] == "PyRDP"


def test_conpot_modbus():
    event = normalize("conpot", {"src_ip": "203.0.113.5", "dst_port": 5020, "data_type": "modbus"})
    assert event["source_ip"] == "203.0.113.5"
    assert event["port"] == 5020
    assert event["service"] == "Modbus"
    assert event["honeypot_type"] == "Conpot"


def test_http_beelzebub_nested_event():
    # Beelzebub nests the request under "event".
    event = normalize("http", {
        "event": {"SourceIp": "192.0.2.7", "HTTPMethod": "GET", "RequestURI": "/"},
        "level": "info",
        "msg": "New Event",
    })
    assert event["source_ip"] == "192.0.2.7"
    assert event["port"] == 80
    assert event["service"] == "HTTP"


def test_wordpress_beelzebub_nested_event():
    event = normalize("wordpress", {
        "event": {"SourceIp": "198.51.100.5", "HTTPMethod": "POST",
                  "RequestURI": "/wp-login.php", "Body": "log=admin&pwd=secret"},
        "msg": "New Event",
    })
    assert event["honeypot_type"] == "Wordpress"
    assert event["source_ip"] == "198.51.100.5"


def test_http_skips_framework_noise():
    # Beelzebub's own startup/info lines have no "event" -> not stored.
    assert normalize("http", {"commands": 0, "level": "info", "msg": "Init service: "}) is None


def test_wordpress_skips_framework_noise():
    assert normalize("wordpress", {"level": "info", "msg": "GetAllServices"}) is None


def test_wordpress_uses_http_fields():
    event = normalize("wordpress", {"src_ip": "192.0.2.44"})
    assert event["port"] == 80
    assert event["honeypot_type"] == "Wordpress"
    assert event["source_ip"] == "192.0.2.44"


def test_unknown_falls_back_to_generic():
    event = normalize("does-not-exist", {"service": "Foo", "port": 9})
    assert event["service"] == "Foo"
    assert event["port"] == 9


def test_bad_payload_does_not_raise():
    event = normalize("cowrie", {})
    assert event["honeypot_type"] == "Cowrie"
    assert event["source_ip"] == ""


def test_generic_field_map_and_static():
    event = normalize(
        "generic",
        {"remote": "203.0.113.9", "dport": "6379"},
        field_map={"source_ip": "remote", "port": "dport"},
        static={"service": "Redis", "honeypot_type": "MyRedis"},
    )
    assert event["source_ip"] == "203.0.113.9"
    assert event["port"] == 6379  # coerced to int
    assert event["service"] == "Redis"
    assert event["honeypot_type"] == "MyRedis"


def test_generic_field_map_dot_notation():
    # Nested payload (e.g. an event wrapped under a key).
    event = normalize(
        "generic",
        {"event": {"client": {"ip": "198.51.100.4"}}, "proto": "ssh"},
        field_map={"source_ip": "event.client.ip", "service": "proto"},
    )
    assert event["source_ip"] == "198.51.100.4"
    assert event["service"] == "ssh"


def test_generic_field_map_precedence_over_payload_canonical():
    # An explicit field_map wins over a canonical-named key already in the payload.
    event = normalize(
        "generic",
        {"source_ip": "10.0.0.1", "real_ip": "203.0.113.1"},
        field_map={"source_ip": "real_ip"},
    )
    assert event["source_ip"] == "203.0.113.1"


def test_generic_missing_mapped_key_is_ignored():
    event = normalize("generic", {"foo": "bar"}, field_map={"source_ip": "nope"})
    assert event["source_ip"] == ""  # base default kept when the path is absent


def test_generic_without_mapping_is_unchanged():
    event = normalize("generic", {"service": "Foo", "port": 9, "source_ip": "1.2.3.4"})
    assert event["service"] == "Foo"
    assert event["port"] == 9
    assert event["source_ip"] == "1.2.3.4"
