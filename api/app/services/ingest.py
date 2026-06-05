"""MQTT event ingest service.

Replaces the standalone HPFeeds broker subscriber
(honeyswarm_broker/file-system/usr/bin/subscriber.py).

Flow:
    agent tails honeypot JSON log -> publishes to ``hive/{id}/events`` ->
    this service normalizes -> writes to MongoDB + indexes to OpenSearch ->
    pushes to the browser WebSocket hub for live view.

Event envelope published by the agent on ``hive/{hive_id}/events``::

    {
        "normalizer": "cowrie",
        "honeypot_instance_id": "<instance object id>",
        "payload": { ...raw honeypot json event... }
    }
"""
import asyncio
import contextlib
import json
import logging
from datetime import datetime

import aiomqtt

from app.core.config import settings
from app.db.opensearch import get_opensearch
from app.models import HoneypotEvent
from app.services.normalizers import normalize
from app.ws.hub import hub

logger = logging.getLogger(__name__)

EVENTS_TOPIC = "hive/+/events"
RECONNECT_DELAY = 5


def _hive_id_from_topic(topic: str) -> str:
    # hive/{hive_id}/events
    parts = topic.split("/")
    return parts[1] if len(parts) >= 3 else "unknown"


async def handle_message(topic: str, raw: bytes) -> None:
    hive_id = _hive_id_from_topic(topic)
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        logger.warning("Dropping malformed event on %s: %s", topic, err)
        return

    payload = envelope.get("payload", {})
    canonical = normalize(envelope.get("normalizer"), payload)

    event = HoneypotEvent(
        date=datetime.utcnow(),
        hive_id=hive_id,
        honeypot_instance_id=envelope.get("honeypot_instance_id"),
        payload=payload,
        **canonical,
    )
    await event.insert()

    doc = event.model_dump(mode="json", exclude={"id"})
    doc["event_id"] = str(event.id)
    try:
        os_client = get_opensearch()
        await os_client.index(index=settings.opensearch_event_index, body=doc, id=str(event.id))
    except Exception as err:  # noqa: BLE001 - OpenSearch must not block ingest
        logger.error("OpenSearch index failed: %s", err)

    await hub.broadcast("events", doc)


async def _run() -> None:
    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username or None,
                password=settings.mqtt_password or None,
            ) as client:
                logger.info("Ingest connected to MQTT, subscribing to %s", EVENTS_TOPIC)
                await client.subscribe(EVENTS_TOPIC)
                async for message in client.messages:
                    await handle_message(str(message.topic), message.payload)
        except aiomqtt.MqttError as err:
            logger.warning("MQTT ingest error (%s); reconnecting in %ss", err, RECONNECT_DELAY)
            await asyncio.sleep(RECONNECT_DELAY)
        except asyncio.CancelledError:
            logger.info("Ingest service stopping")
            raise


class IngestService:
    """Manages the ingest background task lifecycle."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(_run(), name="mqtt-ingest")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


ingest_service = IngestService()
