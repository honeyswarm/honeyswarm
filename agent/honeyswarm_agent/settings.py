"""Agent configuration + persistent local state."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

STATE_DIR = Path(os.environ.get("HONEYSWARM_STATE_DIR", "/var/lib/honeyswarm"))
STATE_FILE = STATE_DIR / "agent.json"
INSTANCES_DIR = STATE_DIR / "instances"

HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))
TAIL_POLL_INTERVAL = float(os.environ.get("TAIL_POLL_INTERVAL", "1.0"))


@dataclass
class AgentConfig:
    controller_url: str
    enroll_token: str | None


def load_config() -> AgentConfig:
    return AgentConfig(
        controller_url=os.environ.get("HONEYSWARM_URL", "http://localhost:8080").rstrip("/"),
        enroll_token=os.environ.get("ENROLL_TOKEN"),
    )


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def instance_dir(instance_id: str) -> Path:
    path = INSTANCES_DIR / instance_id
    path.mkdir(parents=True, exist_ok=True)
    return path
