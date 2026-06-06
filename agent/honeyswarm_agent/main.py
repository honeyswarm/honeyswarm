"""Hive agent entry point.

Enrolls with the controller, then runs an MQTT session:
  * subscribes to ``hive/{id}/commands`` (deploy/start/stop/remove)
  * publishes ``hive/{id}/status`` heartbeats (grains + container states)
  * publishes ``hive/{id}/events`` (tailed honeypot JSON logs)
  * publishes ``hive/{id}/jobs/{command_id}`` (command results)
"""
import asyncio
import json
import logging
import os
import platform
import socket
import ssl

import aiomqtt
import httpx

from . import __version__, runner
from .settings import (
    HEARTBEAT_INTERVAL,
    STATE_DIR,
    AgentConfig,
    load_config,
    load_state,
    save_state,
)
from .tailer import TailerManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("honeyswarm-agent")

RECONNECT_DELAY = 5


def host_facts() -> dict:
    # The agent runs in a container, so resolving our own hostname yields the
    # container's bridge IP (172.17.x.x), not the host's reachable address. The
    # installer (which runs on the host) detects the real values and passes them
    # via HONEYSWARM_HOST_IP / HONEYSWARM_HOST_NAME; fall back to the container's
    # own resolution only when they're absent (e.g. a manual `docker run`).
    host_ip = os.environ.get("HONEYSWARM_HOST_IP", "").strip()
    if host_ip:
        ips = [ip.strip() for ip in host_ip.split(",") if ip.strip()]
    else:
        try:
            ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except OSError:
            ips = []
    return {
        "osfullname": platform.platform(),
        "os": platform.system(),
        "hostname": os.environ.get("HONEYSWARM_HOST_NAME", "").strip() or socket.gethostname(),
        "ipv4": ips,
    }


async def enroll(config: AgentConfig) -> dict:
    """Register with the controller, returning persistent agent state."""
    state = load_state()
    if state.get("hive_id"):
        return state
    if not config.enroll_token:
        raise SystemExit("No saved state and ENROLL_TOKEN not set; cannot enroll.")

    url = f"{config.controller_url}/agent/register"
    logger.info("Enrolling with controller at %s (tls_verify=%s)", url, config.tls_verify)
    async with httpx.AsyncClient(timeout=15, verify=config.tls_verify) as http:
        resp = await http.post(url, json={"token": config.enroll_token, "agent_version": __version__})
        resp.raise_for_status()
        state = resp.json()

    # Persist the broker CA + this hive's client cert/key so we can connect with
    # mutual TLS (now and after restart). The client cert's CN is our hive id;
    # the broker authenticates us as ourselves and the ACL confines us to our own
    # hive/<id>/* subtree.
    if state.get("mqtt_use_tls"):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if state.get("mqtt_ca_cert"):
            ca_path = STATE_DIR / "ca.crt"
            ca_path.write_text(state.pop("mqtt_ca_cert"))
            state["mqtt_ca_path"] = str(ca_path)
        if state.get("mqtt_client_cert") and state.get("mqtt_client_key"):
            cert_path = STATE_DIR / "client.crt"
            key_path = STATE_DIR / "client.key"
            cert_path.write_text(state.pop("mqtt_client_cert"))
            key_path.write_text(state.pop("mqtt_client_key"))
            key_path.chmod(0o600)
            state["mqtt_client_cert_path"] = str(cert_path)
            state["mqtt_client_key_path"] = str(key_path)

    save_state(state)
    logger.info("Enrolled as hive %s", state["hive_id"])
    return state


class Agent:
    def __init__(self, config: AgentConfig, state: dict) -> None:
        self.config = config
        self.state = state
        self.hive_id = state["hive_id"]
        self.client: aiomqtt.Client | None = None
        self.tailers = TailerManager(self._publish_event)
        self.instances: dict[str, dict] = state.get("instances", {})

    # --- topics ---
    @property
    def commands_topic(self) -> str:
        return f"hive/{self.hive_id}/commands"

    def _persist(self) -> None:
        self.state["instances"] = self.instances
        save_state(self.state)

    # --- publishers ---
    async def _publish(self, topic: str, payload: dict) -> None:
        if self.client is None:
            return
        await self.client.publish(topic, json.dumps(payload).encode("utf-8"), qos=1)

    async def _publish_event(self, info: dict, payload: dict) -> None:
        await self._publish(
            f"hive/{self.hive_id}/events",
            {
                "normalizer": info.get("normalizer", "generic"),
                "honeypot_instance_id": info.get("instance_id"),
                "payload": payload,
                # Optional generic-normalizer mapping from the manifest's log: section.
                "field_map": info.get("field_map"),
                "static": info.get("static"),
            },
        )

    async def _publish_progress(self, command_id: str, message: str, instance_id=None) -> None:
        """Tell the controller we've picked up a command and are working on it."""
        await self._publish(
            f"hive/{self.hive_id}/jobs/{command_id}",
            {
                "command_id": command_id,
                "complete": False,
                "status": "running",
                "response": message,
                "instance_id": instance_id,
            },
        )

    async def _publish_job(self, command_id: str, success: bool, response, instance_id=None, instance_status=None) -> None:
        await self._publish(
            f"hive/{self.hive_id}/jobs/{command_id}",
            {
                "command_id": command_id,
                "complete": True,
                "success": success,
                "response": response,
                "instance_id": instance_id,
                "instance_status": instance_status,
            },
        )

    # --- loops ---
    async def _heartbeat_loop(self) -> None:
        while True:
            containers = {
                iid: await asyncio.to_thread(runner.container_status, info["container_name"])
                for iid, info in self.instances.items()
            }
            await self._publish(
                f"hive/{self.hive_id}/status",
                {"agent_version": __version__, "grains": host_facts(), "containers": containers},
            )
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _handle_command(self, command: dict) -> None:
        action = command.get("action")
        command_id = command.get("command_id")
        instance_id = command.get("instance_id")
        if command_id and action in ("deploy", "start", "stop", "remove", "update_agent"):
            await self._publish_progress(command_id, f"{action} in progress", instance_id)
        try:
            if action == "deploy":
                info = await asyncio.to_thread(runner.deploy, command)
                self.instances[instance_id] = info
                self._persist()
                self.tailers.start(info)
                await self._publish_job(command_id, True, "deployed", instance_id, "Running")
            elif action in ("start", "stop", "remove"):
                container_name = command.get("container_name")
                status = await asyncio.to_thread(runner.lifecycle, action, container_name)
                if action == "start" and instance_id in self.instances:
                    self.tailers.start(self.instances[instance_id])
                elif action in ("stop", "remove"):
                    self.tailers.stop(instance_id)
                if action == "remove":
                    self.instances.pop(instance_id, None)
                    self._persist()
                await self._publish_job(command_id, True, status, instance_id, status)
            elif action == "update_agent":
                # Pull the new image + launch the updater (raises on pull failure,
                # leaving us running). Report success first; the updater then
                # recreates this agent after a short settle delay.
                result = await asyncio.to_thread(runner.self_update, command.get("image"))
                await self._publish_job(command_id, True, f"updating to {result['image']}")
            else:
                await self._publish_job(command_id, False, f"unknown action {action}")
        except Exception as err:  # noqa: BLE001 - report failure back to controller
            logger.exception("Command %s failed", action)
            await self._publish_job(command_id, False, str(err), instance_id, "Error")

    def _restore_tailers(self) -> None:
        for info in self.instances.values():
            self.tailers.start(info)

    def _tls_params(self) -> aiomqtt.TLSParameters | None:
        if not self.state.get("mqtt_use_tls"):
            return None
        # Mutual TLS: verify the broker with the CA and present our per-hive
        # client cert (CN == hive id), which the broker maps to our MQTT username.
        return aiomqtt.TLSParameters(
            ca_certs=self.state["mqtt_ca_path"],
            certfile=self.state.get("mqtt_client_cert_path"),
            keyfile=self.state.get("mqtt_client_key_path"),
            cert_reqs=ssl.CERT_REQUIRED,
        )

    async def run(self) -> None:
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self.state["mqtt_host"],
                    port=int(self.state["mqtt_port"]),
                    username=self.state.get("mqtt_username") or None,
                    password=self.state.get("mqtt_password") or None,
                    identifier=f"hive-{self.hive_id}",
                    tls_params=self._tls_params(),
                ) as client:
                    self.client = client
                    logger.info("Connected to MQTT at %s:%s", self.state["mqtt_host"], self.state["mqtt_port"])
                    await client.subscribe(self.commands_topic)
                    self._restore_tailers()
                    hb = asyncio.create_task(self._heartbeat_loop())
                    try:
                        async for message in client.messages:
                            try:
                                command = json.loads(message.payload.decode("utf-8"))
                            except json.JSONDecodeError:
                                continue
                            asyncio.create_task(self._handle_command(command))
                    finally:
                        hb.cancel()
            except aiomqtt.MqttError as err:
                self.client = None
                self.tailers.stop_all()
                logger.warning("MQTT error (%s); reconnecting in %ss", err, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)


async def amain() -> None:
    config = load_config()
    state = await enroll(config)
    agent = Agent(config, state)
    await agent.run()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
