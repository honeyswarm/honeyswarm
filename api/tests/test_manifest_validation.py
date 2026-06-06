"""Unit tests for honeypot manifest editing validation (PUT /honeypots/{id}/manifest)."""
import pytest
import yaml
from fastapi import HTTPException

from app.routers.honeypots import _validate_manifest


def _ok(manifest_yaml: str, config_text=None):
    _validate_manifest(yaml.safe_load(manifest_yaml), config_text)


def test_valid_minimal_manifest():
    _ok("name: X\nimage: img:latest\n")


def test_valid_with_ports_and_udp():
    _ok("name: X\nimage: img\nports:\n  - '80:8800'\n  - '161:16100/udp'\n")


def test_non_mapping_rejected():
    with pytest.raises(HTTPException) as e:
        _validate_manifest("just a string", None)
    assert e.value.status_code == 422


def test_missing_name_rejected():
    with pytest.raises(HTTPException) as e:
        _ok("image: img\n")
    assert e.value.status_code == 422


def test_missing_image_rejected():
    with pytest.raises(HTTPException) as e:
        _ok("name: X\n")
    assert e.value.status_code == 422


def test_bad_port_rejected():
    with pytest.raises(HTTPException):
        _ok("name: X\nimage: img\nports:\n  - '80:abc'\n")


def test_ports_not_a_list_rejected():
    with pytest.raises(HTTPException):
        _ok("name: X\nimage: img\nports: '80:8800'\n")


def test_config_template_requires_config_text():
    manifest = "name: X\nimage: img\nconfig:\n  template: x.cfg\n  mount: /x\n"
    # None (field absent) is rejected...
    with pytest.raises(HTTPException) as e:
        _ok(manifest, config_text=None)
    assert e.value.status_code == 422
    # ...but supplied content — including an empty string while building — passes.
    _ok(manifest, config_text="some = config\n")
    _ok(manifest, config_text="")


def test_command_must_be_str_or_list():
    with pytest.raises(HTTPException):
        _ok("name: X\nimage: img\ncommand:\n  k: v\n")
    _ok("name: X\nimage: img\ncommand:\n  - run\n")
    _ok("name: X\nimage: img\ncommand: run\n")
