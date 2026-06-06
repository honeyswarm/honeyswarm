"""Honeypot definitions (manifest-backed).

A definition is created by importing a manifest from MANIFESTS_DIR, which
snapshots the manifest into the DB (``Honeypot.manifest_data``). The snapshot is
editable from the UI (GET/PUT ``/honeypots/{id}/manifest``) and drives
deployment; the on-disk manifests stay pristine templates.
"""
import logging
import re
from copy import deepcopy
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.manifests import list_manifests, load_manifest
from app.models import Honeypot
from app.services.normalizers import NORMALIZERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/honeypots", tags=["honeypots"])


class ManifestResponse(BaseModel):
    manifest_yaml: str
    config_text: str | None = None
    config_filename: str | None = None


class ManifestUpdate(BaseModel):
    manifest_yaml: str
    config_text: str | None = None


class CreateHoneypot(BaseModel):
    name: str


def _container_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
    return f"honeyswarm_{slug}"


def _starter_manifest(name: str) -> dict[str, Any]:
    """A minimal, valid, deployable manifest to start a custom honeypot from."""
    return {
        "name": name,
        "type": "Custom",
        "description": "Custom honeypot. Edit the manifest (and add a config file if needed).",
        "image": "alpine:latest",
        "container_name": _container_slug(name),
        "ports": ["8080:8080"],
        "log": {"source": "stdout", "normalizer": "generic"},
        "report_fields": ["source_ip"],
    }


def _serialize(hp: Honeypot) -> dict[str, Any]:
    return {
        "id": str(hp.id),
        "name": hp.name,
        "honey_type": hp.honey_type,
        "description": hp.description,
        "container_name": hp.container_name,
        "manifest": hp.manifest,
        "normalizer": hp.normalizer,
        "report_fields": hp.report_fields,
        "has_manifest_data": hp.manifest_data is not None,
    }


def _apply_manifest_fields(hp: Honeypot, manifest: dict[str, Any]) -> None:
    """Set the denormalized Honeypot columns from a manifest dict."""
    hp.manifest_data = manifest
    hp.name = manifest["name"]
    hp.honey_type = manifest.get("type")
    hp.description = manifest.get("description")
    hp.container_name = manifest.get("container_name")
    hp.normalizer = (manifest.get("log") or {}).get("normalizer", "generic")
    hp.report_fields = manifest.get("report_fields", ["source_ip"])


def _validate_manifest(parsed: Any, config_text: str | None) -> None:
    """Structural validation of an edited manifest (raises HTTPException 422)."""
    if not isinstance(parsed, dict):
        raise HTTPException(422, "Manifest must be a YAML mapping")
    if not isinstance(parsed.get("name"), str) or not parsed["name"].strip():
        raise HTTPException(422, "Manifest 'name' is required")
    if not isinstance(parsed.get("image"), str) or not parsed["image"].strip():
        raise HTTPException(422, "Manifest 'image' is required")

    ports = parsed.get("ports")
    if ports is not None:
        if not isinstance(ports, list):
            raise HTTPException(422, "'ports' must be a list of 'host:container[/proto]' strings")
        for entry in ports:
            if not isinstance(entry, str) or ":" not in entry:
                raise HTTPException(422, f"Invalid port mapping: {entry!r} (expected 'host:container[/proto]')")
            host, _, container = entry.partition(":")
            container = container.partition("/")[0]
            if not host.isdigit() or not container.isdigit():
                raise HTTPException(422, f"Invalid port mapping: {entry!r} (host/container must be numbers)")

    command = parsed.get("command")
    if command is not None and not isinstance(command, (str, list)):
        raise HTTPException(422, "'command' must be a string or a list")

    config = parsed.get("config")
    if isinstance(config, dict) and config.get("template") and config_text is None:
        raise HTTPException(422, "This manifest has a config template, so config_text is required")

    log = parsed.get("log")
    if isinstance(log, dict):
        field_map = log.get("field_map")
        if field_map is not None and (
            not isinstance(field_map, dict)
            or not all(isinstance(v, (str, int)) for v in field_map.values())
        ):
            raise HTTPException(422, "log.field_map must be a map of canonical field -> payload key path")
        if log.get("static") is not None and not isinstance(log["static"], dict):
            raise HTTPException(422, "log.static must be a map of canonical field -> value")


@router.get("")
async def list_honeypots() -> list[dict[str, Any]]:
    return [_serialize(hp) async for hp in Honeypot.find_all()]


@router.get("/available")
async def available_manifests() -> list[str]:
    """Manifests on disk that can be imported as honeypot definitions."""
    return list_manifests()


@router.get("/normalizers")
async def list_normalizers() -> list[str]:
    """Event normalizers a custom honeypot can choose for its ``log.normalizer``."""
    return sorted(NORMALIZERS.keys())


@router.post("", status_code=201)
async def create_honeypot(body: CreateHoneypot) -> dict[str, Any]:
    """Create a custom honeypot from a starter manifest (no on-disk source).

    The new definition opens in the manifest editor for the user to flesh out.
    """
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name is required")
    if await Honeypot.find_one(Honeypot.name == name):
        raise HTTPException(409, f"Honeypot '{name}' already exists")

    hp = Honeypot(name=name)  # manifest (provenance) stays None for custom honeypots
    _apply_manifest_fields(hp, _starter_manifest(name))
    await hp.insert()
    return _serialize(hp)


@router.post("/import/{manifest_name}", status_code=201)
async def import_manifest(manifest_name: str) -> dict[str, Any]:
    try:
        manifest = load_manifest(manifest_name)
    except FileNotFoundError as err:
        raise HTTPException(404, str(err))

    name = manifest.get("name", manifest_name)
    if await Honeypot.find_one(Honeypot.name == name):
        raise HTTPException(409, f"Honeypot '{name}' already exists")

    hp = Honeypot(name=name, manifest=manifest_name)
    # manifest may lack an explicit name key; ensure the snapshot carries it.
    manifest = {**manifest, "name": name}
    _apply_manifest_fields(hp, manifest)
    await hp.insert()
    return _serialize(hp)


@router.get("/{honeypot_id}/manifest")
async def get_manifest(honeypot_id: str) -> ManifestResponse:
    hp = await Honeypot.get(honeypot_id)
    if hp is None:
        raise HTTPException(404, "Honeypot not found")

    data = hp.manifest_data
    if data is None:  # legacy doc imported before snapshots existed
        try:
            data = load_manifest(hp.manifest)
        except FileNotFoundError:
            raise HTTPException(404, "No editable manifest for this honeypot")

    data = deepcopy(data)
    config = data.get("config") or {}
    config_text = config.pop("template_content", None)
    config_filename = config.get("template")
    manifest_yaml = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    return ManifestResponse(
        manifest_yaml=manifest_yaml,
        config_text=config_text,
        config_filename=config_filename,
    )


@router.put("/{honeypot_id}/manifest")
async def update_manifest(honeypot_id: str, body: ManifestUpdate) -> dict[str, Any]:
    hp = await Honeypot.get(honeypot_id)
    if hp is None:
        raise HTTPException(404, "Honeypot not found")

    try:
        parsed = yaml.safe_load(body.manifest_yaml)
    except yaml.YAMLError as err:
        raise HTTPException(422, f"Invalid YAML: {err}")

    _validate_manifest(parsed, body.config_text)

    # Re-inline the config text the UI edits as a separate field.
    config = parsed.get("config")
    if isinstance(config, dict) and config.get("template"):
        config["template_content"] = body.config_text or ""

    new_name = parsed["name"]
    if new_name != hp.name:
        clash = await Honeypot.find_one(Honeypot.name == new_name)
        if clash is not None and clash.id != hp.id:
            raise HTTPException(409, f"Honeypot '{new_name}' already exists")

    _apply_manifest_fields(hp, parsed)
    await hp.save()
    return _serialize(hp)


@router.delete("/{honeypot_id}", status_code=204)
async def delete_honeypot(honeypot_id: str) -> None:
    hp = await Honeypot.get(honeypot_id)
    if hp is None:
        raise HTTPException(404, "Honeypot not found")
    await hp.delete()
