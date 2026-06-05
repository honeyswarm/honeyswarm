"""Agent-facing endpoints (called by the hive agent, not the browser).

Replaces the Salt minion key-accept handshake. The agent presents its one-time
enrollment token and receives its hive id + MQTT connection details.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import hash_token
from app.models import Hive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class RegisterRequest(BaseModel):
    token: str
    agent_version: str | None = None


@router.post("/register")
async def register(body: RegisterRequest) -> dict:
    token_hash = hash_token(body.token)
    hive = await Hive.find_one(Hive.agent_token_hash == token_hash)
    if hive is None:
        raise HTTPException(401, "Invalid enrollment token")

    hive.registered = True
    hive.mqtt_username = str(hive.id)
    if body.agent_version:
        hive.agent_version = body.agent_version
    await hive.save()

    logger.info("Hive %s (%s) registered", hive.name, hive.id)
    return {
        "hive_id": str(hive.id),
        "mqtt_host": settings.mqtt_public_host,
        "mqtt_port": settings.mqtt_port,
        "mqtt_username": settings.mqtt_username,  # dev: shared; prod: per-hive creds
        "mqtt_password": settings.mqtt_password,
    }
