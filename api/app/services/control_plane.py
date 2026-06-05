"""MQTT control plane (controller side).

Replaces the Salt master interaction (saltapi.py / functions.py polling).

* Publishes commands to ``hive/{id}/commands`` (deploy/start/stop/remove).
* Subscribes to ``hive/{id}/status`` (heartbeat: grains + container states) and
  ``hive/{id}/jobs/{command_id}`` (command results) to update Mongo docs.

Heartbeat-driven liveness replaces the old APScheduler poll_hives/poll_instances.
"""
import asyncio
import contextlib
import json
import logging
from datetime import datetime

import aiomqtt
from beanie import PydanticObjectId

from app.core.config import settings
from app.core.mqtt import tls_params
from app.models import Hive, HoneypotInstance, Job
from app.models.documents import ConnectionState
from app.ws.hub import hub

logger = logging.getLogger(__name__)

STATUS_TOPIC = "hive/+/status"
JOBS_TOPIC = "hive/+/jobs/+"
RECONNECT_DELAY = 5


def _hive_id_from_topic(topic: str) -> str:
    return topic.split("/")[1]


async def _get_hive(hive_id: str) -> Hive | None:
    try:
        return await Hive.get(PydanticObjectId(hive_id))
    except Exception:  # noqa: BLE001 - bad id => no hive
        return None


async def _handle_status(hive_id: str, data: dict) -> None:
    hive = await _get_hive(hive_id)
    if hive is None:
        logger.warning("Status from unknown hive %s", hive_id)
        return
    hive.last_heartbeat = datetime.utcnow()
    hive.last_seen = hive.last_heartbeat
    hive.connection_state = ConnectionState.ONLINE
    if "grains" in data:
        hive.grains = data["grains"]
    if "agent_version" in data:
        hive.agent_version = data["agent_version"]
    await hive.save()

    # Reflect reported container states onto instances.
    for instance_id, state in (data.get("containers") or {}).items():
        try:
            instance = await HoneypotInstance.get(PydanticObjectId(instance_id))
        except Exception:  # noqa: BLE001
            continue
        if instance:
            instance.status = state
            await instance.save()

    await hub.broadcast("hive_status", {"hive_id": hive_id, "grains": hive.grains})


async def _handle_job(hive_id: str, command_id: str, data: dict) -> None:
    job = await Job.find_one(Job.command_id == command_id)
    if job is None:
        logger.warning("Result for unknown command %s", command_id)
        return
    job.complete = bool(data.get("complete", True))
    job.completed_at = datetime.utcnow()
    job.last_check = job.completed_at
    job.job_response = json.dumps(data.get("response", data))
    await job.save()

    # Update the instance status from the command outcome if provided.
    if data.get("instance_id") and data.get("instance_status"):
        try:
            instance = await HoneypotInstance.get(PydanticObjectId(data["instance_id"]))
            if instance:
                instance.status = data["instance_status"]
                await instance.save()
        except Exception:  # noqa: BLE001
            pass

    await hub.broadcast("job", {"command_id": command_id, "complete": job.complete})


async def _handle(topic: str, raw: bytes) -> None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Malformed control message on %s", topic)
        return
    parts = topic.split("/")
    hive_id = parts[1]
    kind = parts[2]
    if kind == "status":
        await _handle_status(hive_id, data)
    elif kind == "jobs" and len(parts) >= 4:
        await _handle_job(hive_id, parts[3], data)


class ControlPlane:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._client: aiomqtt.Client | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="control-plane")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_username or None,
                    password=settings.mqtt_password or None,
                    tls_params=tls_params(),
                ) as client:
                    self._client = client
                    logger.info("Control plane connected to MQTT")
                    await client.subscribe(STATUS_TOPIC)
                    await client.subscribe(JOBS_TOPIC)
                    async for message in client.messages:
                        await _handle(str(message.topic), message.payload)
            except aiomqtt.MqttError as err:
                self._client = None
                logger.warning("Control plane MQTT error (%s); reconnecting", err)
                await asyncio.sleep(RECONNECT_DELAY)
            except asyncio.CancelledError:
                raise

    async def publish_command(self, hive_id: str, command: dict) -> None:
        if self._client is None:
            raise RuntimeError("Control plane not connected to MQTT")
        topic = f"hive/{hive_id}/commands"
        await self._client.publish(topic, json.dumps(command).encode("utf-8"), qos=1)
        logger.info("Published %s command to %s", command.get("action"), topic)


control_plane = ControlPlane()
