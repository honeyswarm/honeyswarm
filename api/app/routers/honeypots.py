"""Honeypot definitions (manifest-backed).

Replaces the old honeypots blueprint. A definition is created by importing a
manifest from MANIFESTS_DIR; the manifest drives deployment.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.manifests import list_manifests, load_manifest
from app.models import Honeypot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/honeypots", tags=["honeypots"])


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
    }


@router.get("")
async def list_honeypots() -> list[dict[str, Any]]:
    return [_serialize(hp) async for hp in Honeypot.find_all()]


@router.get("/available")
async def available_manifests() -> list[str]:
    """Manifests on disk that can be imported as honeypot definitions."""
    return list_manifests()


@router.post("/import/{manifest_name}", status_code=201)
async def import_manifest(manifest_name: str) -> dict[str, Any]:
    try:
        manifest = load_manifest(manifest_name)
    except FileNotFoundError as err:
        raise HTTPException(404, str(err))

    name = manifest.get("name", manifest_name)
    if await Honeypot.find_one(Honeypot.name == name):
        raise HTTPException(409, f"Honeypot '{name}' already exists")

    hp = Honeypot(
        name=name,
        honey_type=manifest.get("type"),
        description=manifest.get("description"),
        container_name=manifest.get("container_name"),
        manifest=manifest_name,
        normalizer=(manifest.get("log") or {}).get("normalizer", "generic"),
        report_fields=manifest.get("report_fields", ["source_ip"]),
    )
    await hp.insert()
    return _serialize(hp)


@router.delete("/{honeypot_id}", status_code=204)
async def delete_honeypot(honeypot_id: str) -> None:
    hp = await Honeypot.get(honeypot_id)
    if hp is None:
        raise HTTPException(404, "Honeypot not found")
    await hp.delete()
