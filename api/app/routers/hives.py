"""Hive management + enrollment.

Replaces the Salt-minion registration flow (hives/api/hive/register/<os> +
salt key accept). Creating a hive issues a one-time enrollment token and an
install one-liner; the agent later calls /agent/register with that token.
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import generate_token, hash_token
from app.models import Hive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hives", tags=["hives"])


class HiveCreate(BaseModel):
    name: str


def _serialize(hive: Hive) -> dict[str, Any]:
    return {
        "id": str(hive.id),
        "name": hive.name,
        "registered": hive.registered,
        "connection_state": hive.connection_state,
        "agent_version": hive.agent_version,
        "last_heartbeat": hive.last_heartbeat,
        "grains": hive.grains,
        "event_count": hive.event_count,
    }


@router.get("")
async def list_hives() -> list[dict[str, Any]]:
    return [_serialize(h) async for h in Hive.find_all()]


@router.post("", status_code=201)
async def create_hive(body: HiveCreate) -> dict[str, Any]:
    if await Hive.find_one(Hive.name == body.name):
        raise HTTPException(409, "A hive with that name already exists")
    token = generate_token()
    hive = Hive(name=body.name, agent_token_hash=hash_token(token))
    await hive.insert()
    install_command = (
        f"docker run -d --name honeyswarm-agent --restart unless-stopped "
        f"-v /var/run/docker.sock:/var/run/docker.sock "
        f"-v honeyswarm_agent_state:/var/lib/honeyswarm "
        f"-e HONEYSWARM_URL={settings.public_url} "
        f"-e ENROLL_TOKEN={token} "
        f"{settings.agent_image}"
    )
    result = _serialize(hive)
    result["enroll_token"] = token  # shown once at creation time
    result["install_command"] = install_command
    return result


@router.get("/{hive_id}")
async def get_hive(hive_id: str) -> dict[str, Any]:
    hive = await Hive.get(hive_id)
    if hive is None:
        raise HTTPException(404, "Hive not found")
    return _serialize(hive)


@router.delete("/{hive_id}", status_code=204)
async def delete_hive(hive_id: str) -> None:
    hive = await Hive.get(hive_id)
    if hive is None:
        raise HTTPException(404, "Hive not found")
    await hive.delete()
