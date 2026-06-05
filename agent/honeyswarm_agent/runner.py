"""Docker SDK manifest executor.

Replaces the docker_container.running / docker.start / docker.stop / docker.rm
Salt operations. docker-py is synchronous, so callers wrap these in
asyncio.to_thread.
"""
import logging
import os
from pathlib import Path
from typing import Any

import docker
from docker.errors import NotFound

from .settings import instance_dir

logger = logging.getLogger(__name__)

_client = None

# Named, vetted host-setup actions (replaces the old arbitrary cmd.run sed).
KNOWN_HOST_SETUP = {"move-sshd-off-22"}


def client() -> "docker.DockerClient":
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def render_template(content: str, variables: dict[str, Any]) -> str:
    """Substitute UPPERCASE placeholders (e.g. INSTANCEID) in a config template.

    Mirrors the legacy sed-based substitution but done safely in-process.
    """
    rendered = content
    for key, value in variables.items():
        rendered = rendered.replace(str(key), str(value))
    return rendered


def _parse_ports(ports: list[str]) -> dict[str, int]:
    # "22:2222" => host 22 -> container 2222 ; docker-py wants {"2222/tcp": 22}
    mapping: dict[str, int] = {}
    for entry in ports or []:
        host, _, container = entry.partition(":")
        mapping[f"{container}/tcp"] = int(host)
    return mapping


def apply_host_setup(actions: list[str]) -> None:
    for action in actions or []:
        if action not in KNOWN_HOST_SETUP:
            logger.warning("Ignoring unknown host_setup action: %s", action)
            continue
        # Host mutation only makes sense when the agent runs with host access.
        # Kept best-effort and non-fatal so it never blocks a deploy.
        if action == "move-sshd-off-22":
            logger.info("host_setup move-sshd-off-22 (no-op unless host access configured)")


def deploy(command: dict) -> dict:
    """Create (replacing any existing) and start a honeypot container.

    Returns tailer info: {mode, normalizer, host_log_path, container_name}.
    """
    manifest = command["manifest"]
    instance_id = command["instance_id"]
    container_name = command["container_name"]
    variables = command.get("vars", {})
    apply_host_setup(manifest.get("host_setup"))

    idir = instance_dir(instance_id)
    volumes: dict[str, dict] = {}

    # Config template -> rendered file bind-mounted into the container.
    config = manifest.get("config") or {}
    if config.get("template_content") and config.get("mount"):
        rendered = render_template(config["template_content"], variables)
        cfg_path = idir / Path(config["template"]).name
        cfg_path.write_text(rendered)
        volumes[str(cfg_path)] = {"bind": config["mount"], "mode": "rw"}

    # Logging: 'file' => bind a host log dir we can tail; 'stdout' => docker logs.
    log = manifest.get("log") or {}
    mode = log.get("source", "stdout")
    host_log_path = None
    if mode == "file" and log.get("path"):
        log_dir = idir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o777)  # honeypot container may run as non-root
        container_log_dir = str(Path(log["path"]).parent)
        volumes[str(log_dir)] = {"bind": container_log_dir, "mode": "rw"}
        host_log_path = str(log_dir / Path(log["path"]).name)

    cli = client()
    # Replace any existing container with this name.
    try:
        existing = cli.containers.get(container_name)
        existing.remove(force=True)
        logger.info("Removed existing container %s", container_name)
    except NotFound:
        pass

    cli.containers.run(
        manifest["image"],
        name=container_name,
        detach=True,
        ports=_parse_ports(manifest.get("ports")),
        volumes=volumes or None,
        command=manifest.get("command"),
        environment=manifest.get("env"),
        restart_policy={"Name": "unless-stopped"},
    )
    logger.info("Deployed container %s from %s", container_name, manifest["image"])

    return {
        "mode": mode,
        "normalizer": log.get("normalizer", "generic"),
        "host_log_path": host_log_path,
        "container_name": container_name,
        "instance_id": instance_id,
    }


def lifecycle(action: str, container_name: str) -> str:
    """start / stop / remove a container. Returns the resulting status."""
    cli = client()
    try:
        container = cli.containers.get(container_name)
    except NotFound:
        return "Missing"
    if action == "start":
        container.start()
        return "Running"
    if action == "stop":
        container.stop()
        return "Stopped"
    if action == "remove":
        container.remove(force=True)
        return "Removed"
    return "Unknown"


def container_status(container_name: str) -> str:
    cli = client()
    try:
        return cli.containers.get(container_name).status.capitalize()
    except NotFound:
        return "Missing"
