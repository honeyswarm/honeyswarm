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
