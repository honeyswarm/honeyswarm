"""Honeypot instances: deploy / start / stop / remove on a hive.

Replaces saltapi.apply_state / docker_control / docker_remove. Each action
creates a Job and publishes a command to the hive over MQTT; the agent reports
results back on hive/{id}/jobs/{command_id}, handled by the control plane.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.manifests import load_manifest
from app.core.refs import link_id
from app.models import Hive, Honeypot, HoneypotInstance, Job
from app.services.control_plane import control_plane

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instances", tags=["instances"])


class DeployRequest(BaseModel):
    honeypot_id: str
    hive_id: str
    vars: dict[str, Any] = {}


def _serialize(inst: HoneypotInstance) -> dict[str, Any]:
    return {
        "id": str(inst.id),
        "honeypot": link_id(inst.honeypot),
        "hive": link_id(inst.hive),
        "status": inst.status,
        "pillar": inst.pillar,
    }


async def _dispatch(hive: Hive, job_type: str, command: dict, description: str) -> Job:
    """Create a tracking Job and publish its command to the hive."""
    job = Job(job_type=job_type, job_short=job_type, job_description=description, hive=hive)
    await job.insert()
    command["command_id"] = str(job.id)
    job.command_id = str(job.id)
    await job.save()
    try:
        await control_plane.publish_command(str(hive.id), command)
    except RuntimeError as err:
        raise HTTPException(503, f"Control plane unavailable: {err}")
    return job


@router.get("")
async def list_instances() -> list[dict[str, Any]]:
    return [_serialize(i) async for i in HoneypotInstance.find_all()]


@router.post("/deploy", status_code=201)
async def deploy(body: DeployRequest) -> dict[str, Any]:
    honeypot = await Honeypot.get(body.honeypot_id)
    if honeypot is None:
        raise HTTPException(404, "Honeypot not found")
    hive = await Hive.get(body.hive_id)
    if hive is None:
        raise HTTPException(404, "Hive not found")
    if not hive.registered:
        raise HTTPException(409, "Hive is not registered")

    # Prefer the editable DB snapshot; fall back to disk for legacy definitions.
    if honeypot.manifest_data:
        manifest = honeypot.manifest_data
    else:
        try:
            manifest = load_manifest(honeypot.manifest)
        except FileNotFoundError as err:
            raise HTTPException(404, str(err))

    instance = HoneypotInstance(honeypot=honeypot, hive=hive, status="Pending")
    await instance.insert()

    container_name = f"{manifest.get('container_name', 'honeyswarm')}_{str(instance.id)[:8]}"
    merged_vars = {**(manifest.get("vars") or {}), **body.vars, "INSTANCEID": str(instance.id)}
    instance.pillar = {"container_name": container_name, "vars": merged_vars}
    await instance.save()

    command = {
        "action": "deploy",
        "instance_id": str(instance.id),
        "container_name": container_name,
        "manifest": manifest,
        "vars": merged_vars,
    }
    job = await _dispatch(hive, "deploy", command, f"Deploy {honeypot.name}")
    return {"instance": _serialize(instance), "command_id": job.command_id}


async def _lifecycle(instance_id: str, action: str) -> dict[str, Any]:
    instance = await HoneypotInstance.get(instance_id)
    if instance is None:
        raise HTTPException(404, "Instance not found")
    hive = await instance.hive.fetch() if instance.hive else None
    if hive is None:
        raise HTTPException(409, "Instance has no hive")
    command = {
        "action": action,
        "instance_id": str(instance.id),
        "container_name": (instance.pillar or {}).get("container_name"),
    }
    job = await _dispatch(hive, action, command, f"{action} instance {instance.id}")
    return {"command_id": job.command_id}


@router.post("/{instance_id}/start")
async def start(instance_id: str) -> dict[str, Any]:
    return await _lifecycle(instance_id, "start")


@router.post("/{instance_id}/stop")
async def stop(instance_id: str) -> dict[str, Any]:
    return await _lifecycle(instance_id, "stop")


@router.delete("/{instance_id}")
async def remove(instance_id: str) -> dict[str, Any]:
    result = await _lifecycle(instance_id, "remove")
    instance = await HoneypotInstance.get(instance_id)
    if instance:
        await instance.delete()
    return result
