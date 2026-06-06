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
from app.core.mqtt_certs import issue_client_cert
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
        .replace("__AGENT_TLS_VERIFY__", "true" if settings.agent_tls_verify else "false")
    )


class RegisterRequest(BaseModel):
    token: str
    agent_version: str | None = None


# Enrollment tokens are secrets.token_urlsafe() => URL-safe base64 chars only.
# Restricting the charset prevents reflected shell/PowerShell injection in the
# rendered installer (which is meant to be piped to `sudo bash` / `iex`).
TOKEN_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"


async def _require_enroll_token(token: str) -> None:
    """Reject tokens that don't correspond to a real pending enrollment."""
    if await Hive.find_one(Hive.agent_token_hash == hash_token(token)) is None:
        raise HTTPException(404, "Unknown enrollment token")


@router.get("/install.sh", response_class=PlainTextResponse)
async def install_sh(token: str = Query(..., pattern=TOKEN_PATTERN)) -> str:
    """Linux installer: `curl -fsSL <url>/agent/install.sh?token=… | sudo bash`."""
    await _require_enroll_token(token)
    return _render_installer("install.sh", token)


@router.get("/install.ps1", response_class=PlainTextResponse)
async def install_ps1(token: str = Query(..., pattern=TOKEN_PATTERN)) -> str:
    """Windows installer: `irm <url>/agent/install.ps1?token=… | iex`."""
    await _require_enroll_token(token)
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

    response: dict = {
        "hive_id": str(hive.id),
        "mqtt_host": settings.mqtt_public_host,
        "mqtt_port": settings.mqtt_port,
        # The broker derives the username from the client cert CN; we echo it for
        # the agent's logs/connection identifier. No shared password under mTLS.
        "mqtt_username": str(hive.id),
        "mqtt_use_tls": settings.mqtt_use_tls,
    }

    # Mutual TLS: ship the broker CA (to verify the broker) plus a per-hive client
    # certificate (CN == hive id) so the broker authenticates this hive as itself
    # and the ACL confines it to its own hive/<id>/* subtree. This replaces the
    # old single shared credential, so a compromised hive cannot impersonate or
    # command any other hive.
    if settings.mqtt_use_tls:
        ca_path = Path(settings.mqtt_ca_cert)
        if ca_path.exists():
            response["mqtt_ca_cert"] = ca_path.read_text()
        else:
            logger.warning("MQTT CA cert not found at %s", ca_path)
            response["mqtt_ca_cert"] = ""
        try:
            cert_pem, key_pem = issue_client_cert(str(hive.id))
            response["mqtt_client_cert"] = cert_pem
            response["mqtt_client_key"] = key_pem
        except (OSError, ValueError) as err:
            logger.error("Could not mint MQTT client cert for hive %s: %s", hive.id, err)
            raise HTTPException(500, "Broker certificate authority unavailable")

    logger.info("Hive %s (%s) registered", hive.name, hive.id)
    return response
