"""Agent-facing endpoints (called by the hive agent, not the browser).

Replaces the Salt minion key-accept handshake. The agent presents its one-time
enrollment token and receives its hive id + MQTT connection details.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import hash_token
from app.models import Hive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

INSTALL_DIR = Path(__file__).resolve().parent.parent / "agent_install"


def _render_installer(filename: str, token: str) -> str:
    template = (INSTALL_DIR / filename).read_text()
    return (
        template.replace("__HONEYSWARM_URL__", settings.public_url)
        .replace("__ENROLL_TOKEN__", token)
        .replace("__AGENT_IMAGE__", settings.agent_image)
    )


class RegisterRequest(BaseModel):
    token: str
    agent_version: str | None = None


@router.get("/install.sh", response_class=PlainTextResponse)
async def install_sh(token: str = Query(...)) -> str:
    """Linux installer: `curl -fsSL <url>/agent/install.sh?token=… | sudo bash`."""
    return _render_installer("install.sh", token)


@router.get("/install.ps1", response_class=PlainTextResponse)
async def install_ps1(token: str = Query(...)) -> str:
    """Windows installer: `irm <url>/agent/install.ps1?token=… | iex`."""
    return _render_installer("install.ps1", token)


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

    # Ship the self-signed CA so the agent can verify the broker over TLS.
    ca_cert = ""
    if settings.mqtt_use_tls:
        ca_path = Path(settings.mqtt_ca_cert)
        if ca_path.exists():
            ca_cert = ca_path.read_text()
        else:
            logger.warning("MQTT CA cert not found at %s", ca_path)

    logger.info("Hive %s (%s) registered", hive.name, hive.id)
    return {
        "hive_id": str(hive.id),
        "mqtt_host": settings.mqtt_public_host,
        "mqtt_port": settings.mqtt_port,
        "mqtt_username": settings.mqtt_username,  # dev: shared; prod: per-hive creds
        "mqtt_password": settings.mqtt_password,
        "mqtt_use_tls": settings.mqtt_use_tls,
        "mqtt_ca_cert": ca_cert,
    }
