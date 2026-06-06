"""One-shot agent self-updater.

Launched (detached) by ``runner.self_update`` from the freshly pulled agent
image. It outlives the old agent container, removes it, and recreates it from
the captured run spec with the new image — preserving the agent's binds (so its
persistent state under /var/lib/honeyswarm survives) and enrollment.

Run as: ``python -m honeyswarm_agent.updater`` with ``HONEYSWARM_UPDATE_SPEC``
set to the JSON spec produced by ``runner._recreate_spec``.

Fail-safe: if the new image fails to start the recreated agent, it rolls back to
the previous image. If this updater itself never runs (e.g. the new image is
broken), the old agent is never removed and simply keeps running.
"""
import json
import logging
import os
import time

import docker
from docker.errors import NotFound

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("honeyswarm-agent-updater")

# Give the old agent a moment to publish its "updating" job result over MQTT
# before we remove it.
SETTLE_SECONDS = float(os.environ.get("HONEYSWARM_UPDATE_SETTLE", "4"))


def _run_agent(cli: "docker.DockerClient", image: str, spec: dict) -> None:
    cli.containers.run(
        image,
        name=spec["name"],
        detach=True,
        volumes=spec.get("binds") or None,
        environment=spec.get("environment") or None,
        network_mode=spec.get("network_mode") or "default",
        restart_policy=spec.get("restart_policy") or {"Name": "unless-stopped"},
    )


def main() -> None:
    spec = json.loads(os.environ["HONEYSWARM_UPDATE_SPEC"])
    cli = docker.from_env()
    name = spec["name"]

    time.sleep(SETTLE_SECONDS)

    try:
        cli.containers.get(name).remove(force=True)
        logger.info("Removed old agent container %s", name)
    except NotFound:
        pass

    try:
        _run_agent(cli, spec["image"], spec)
        logger.info("Recreated agent %s from %s", name, spec["image"])
    except Exception:  # noqa: BLE001 - on failure, roll back to the old image
        fallback = spec.get("fallback_image")
        logger.exception("New image %s failed to start; rolling back to %s", spec["image"], fallback)
        if fallback and fallback != spec["image"]:
            _run_agent(cli, fallback, spec)
            logger.info("Rolled back agent %s to %s", name, fallback)


if __name__ == "__main__":
    main()
