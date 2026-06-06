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
    base = settings.public_url.rstrip("/")
    # One-liners that fetch a per-hive install script (installs Docker + runs the agent).
    install_command = f'curl -fsSL "{base}/agent/install.sh?token={token}" | sudo bash'
    # Same, but also relocates the host SSH daemon off :22 so an SSH honeypot can bind it.
    install_command_ssh = (
        f'curl -fsSL "{base}/agent/install.sh?token={token}" | sudo bash -s -- --move-ssh 2222'
    )
    install_command_windows = f'irm "{base}/agent/install.ps1?token={token}" | iex'
    result = _serialize(hive)
    result["enroll_token"] = token  # shown once at creation time
    result["install_command"] = install_command
    result["install_command_ssh"] = install_command_ssh
    result["install_command_windows"] = install_command_windows
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
