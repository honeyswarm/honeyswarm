"""Docker SDK manifest executor.

Replaces the docker_container.running / docker.start / docker.stop / docker.rm
Salt operations. docker-py is synchronous, so callers wrap these in
asyncio.to_thread.
"""
import json
import logging
import os
import socket
from pathlib import Path
from typing import Any

import docker
from docker.errors import NotFound

from .settings import instance_dir

logger = logging.getLogger(__name__)

_client = None

# Named, vetted host-setup actions (replaces the old arbitrary cmd.run sed).
KNOWN_HOST_SETUP = {"move-sshd-off-22"}

# Self-update: only these env vars are carried onto the recreated agent, so the
# new image's own baked defaults (PATH, LANG, ...) are not shadowed by old ones.
_AGENT_ENV_PREFIXES = ("HONEYSWARM", "ENROLL", "HEARTBEAT", "TAIL_POLL", "AGENT_IMAGE")
UPDATER_CONTAINER_NAME = "honeyswarm-agent-updater"
DOCKER_SOCK = "/var/run/docker.sock"


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


def _free_honeyswarm_ports(cli, host_ports: set[int], keep: str) -> None:
    """Remove honeyswarm honeypot containers binding any of ``host_ports``.

    Honeypots bind fixed host ports (e.g. 22), so only one can run per hive.
    This clears orphans from prior instances / failed deploys so a redeploy
    isn't blocked by 'port is already allocated'. Scoped to honeyswarm_*
    containers so unrelated workloads are never touched.
    """
    if not host_ports:
        return
    for container in cli.containers.list(all=True):
        if container.name == keep or not container.name.startswith("honeyswarm_"):
            continue
        bindings = (container.attrs.get("HostConfig", {}) or {}).get("PortBindings") or {}
        used = {
            int(b["HostPort"])
            for binds in bindings.values()
            for b in (binds or [])
            if b.get("HostPort")
        }
        if used & host_ports:
            logger.info(
                "Removing orphan %s holding host port(s) %s",
                container.name, sorted(used & host_ports),
            )
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass


def _parse_ports(ports: list[str]) -> dict[str, int]:
    # "22:2222"      => host 22 -> container 2222/tcp ; docker-py wants {"2222/tcp": 22}
    # "161:16100/udp" => host 161 -> container 16100/udp (proto defaults to tcp)
    mapping: dict[str, int] = {}
    for entry in ports or []:
        host, _, container = entry.partition(":")
        proto = "tcp"
        if "/" in container:
            container, _, proto = container.partition("/")
        mapping[f"{container}/{proto}"] = int(host)
    return mapping


def apply_host_setup(actions: list[str]) -> None:
    for action in actions or []:
        if action not in KNOWN_HOST_SETUP:
            logger.warning("Ignoring unknown host_setup action: %s", action)
            continue
        # Host mutation only makes sense when the agent runs with host access.
        # Kept best-effort and non-fatal so it never blocks a deploy.
        if action == "move-sshd-off-22":
            # The agent runs in a container and can't change host SSH config.
            # Operators free port 22 at install time: install.sh --move-ssh <port>.
            logger.info(
                "host_setup move-sshd-off-22: no-op in container; re-run the hive "
                "installer with --move-ssh <port> if port 22 is in use on the host"
            )


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
    ports = _parse_ports(manifest.get("ports"))

    # Substitute instance vars (UPPERCASE placeholders) into command args too,
    # so a manifest can parameterise its command (e.g. PyRDP's relay target).
    command = manifest.get("command")
    if command is not None:
        if isinstance(command, list):
            command = [render_template(str(arg), variables) for arg in command]
        else:
            command = render_template(str(command), variables)

    # Replace any existing container with this name.
    try:
        cli.containers.get(container_name).remove(force=True)
        logger.info("Removed existing container %s", container_name)
    except NotFound:
        pass

    # Clear orphaned honeyswarm honeypots holding the host ports we need (e.g. a
    # previous instance, or a half-started container from a failed deploy).
    _free_honeyswarm_ports(cli, set(ports.values()), keep=container_name)

    try:
        cli.containers.run(
            manifest["image"],
            name=container_name,
            detach=True,
            ports=ports,
            volumes=volumes or None,
            command=command,
            environment=manifest.get("env"),
            restart_policy={"Name": "unless-stopped"},
        )
    except Exception:
        # Don't leave a half-created container reserving the port.
        try:
            cli.containers.get(container_name).remove(force=True)
        except NotFound:
            pass
        raise
    logger.info("Deployed container %s from %s", container_name, manifest["image"])

    return {
        "mode": mode,
        "normalizer": log.get("normalizer", "generic"),
        # Optional generic-normalizer mapping, shipped with each event so the
        # controller can map a custom honeypot's JSON without code.
        "field_map": log.get("field_map"),
        "static": log.get("static"),
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


# --- self-update -----------------------------------------------------------
#
# The agent runs as a container and has the host Docker socket, but it can't
# replace its own container directly (removing itself would kill the process
# mid-operation). So it pulls the new image, then launches a short-lived
# *updater* container (from that new image) which outlives the agent, removes
# it, and recreates it from the captured run spec. See honeyswarm_agent.updater.


def _self_container(cli: "docker.DockerClient"):
    """Locate the agent's own container.

    Docker sets a container's hostname to its (short) id by default, so
    ``socket.gethostname()`` resolves back to us; fall back to an explicit env
    override or the conventional install name.
    """
    for ident in (
        os.environ.get("HONEYSWARM_AGENT_CONTAINER"),
        socket.gethostname(),
        "honeyswarm-agent",
    ):
        if not ident:
            continue
        try:
            return cli.containers.get(ident)
        except NotFound:
            continue
    raise RuntimeError("Could not locate the agent's own container for self-update")


def _agent_env(env_list: list[str]) -> list[str]:
    """Keep only honeyswarm-relevant env vars (don't shadow the new image's)."""
    return [
        kv for kv in (env_list or [])
        if any(kv.split("=", 1)[0].startswith(p) for p in _AGENT_ENV_PREFIXES)
    ]


def _recreate_spec(attrs: dict, image: str) -> dict:
    """Build a docker-run spec from the agent's own container config."""
    host = attrs.get("HostConfig", {}) or {}
    cfg = attrs.get("Config", {}) or {}
    rp = host.get("RestartPolicy") or {}
    return {
        "name": (attrs.get("Name") or "").lstrip("/") or "honeyswarm-agent",
        "image": image,
        "environment": _agent_env(cfg.get("Env")),
        "binds": list(host.get("Binds") or []),
        "network_mode": host.get("NetworkMode") or "default",
        "restart_policy": {
            "Name": rp.get("Name") or "unless-stopped",
            "MaximumRetryCount": rp.get("MaximumRetryCount", 0),
        },
    }


def self_update(image: str | None = None) -> dict:
    """Pull a new agent image and launch the updater that recreates us.

    Returns once the updater is launched; the updater then replaces this agent.
    Raising here (e.g. pull failure) leaves the running agent untouched.
    """
    cli = client()
    me = _self_container(cli)
    current_image = (me.attrs.get("Config", {}) or {}).get("Image")
    target = image or current_image
    if not target:
        raise RuntimeError("No target image for self-update")

    logger.info("Self-update: pulling %s", target)
    cli.images.pull(target)

    spec = _recreate_spec(me.attrs, target)
    spec["fallback_image"] = current_image  # roll back if the new image won't run

    # Clear any leftover updater from a previous attempt, then launch a fresh one
    # from the new image. It mounts the Docker socket and runs the updater module.
    try:
        cli.containers.get(UPDATER_CONTAINER_NAME).remove(force=True)
    except NotFound:
        pass
    cli.containers.run(
        target,
        command=["python", "-m", "honeyswarm_agent.updater"],
        name=UPDATER_CONTAINER_NAME,
        detach=True,
        remove=True,
        volumes={DOCKER_SOCK: {"bind": DOCKER_SOCK, "mode": "rw"}},
        environment={"HONEYSWARM_UPDATE_SPEC": json.dumps(spec)},
    )
    logger.info("Updater launched; agent %s will be recreated from %s", spec["name"], target)
    return {"image": target, "container": spec["name"]}
