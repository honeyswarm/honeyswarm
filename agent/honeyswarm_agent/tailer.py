"""Honeypot JSON-log tailers.

Replaces HPFeeds: read each honeypot's native JSON log and publish one MQTT
envelope per event to ``hive/{id}/events``. The controller does normalization,
so the agent only attaches the normalizer name + instance id.

Two modes:
* ``file``   -- poll a bind-mounted host log file for new lines.
* ``stdout`` -- stream ``docker logs`` for the container.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Awaitable, Callable

from . import runner
from .settings import TAIL_POLL_INTERVAL

logger = logging.getLogger(__name__)

# publisher(normalizer, instance_id, payload_dict) -> awaitable
Publisher = Callable[[str, str, dict], Awaitable[None]]


async def _emit_line(line: str, normalizer: str, instance_id: str, publish: Publisher) -> None:
    line = line.strip()
    if not line:
        return
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return  # non-JSON log noise
    await publish(normalizer, instance_id, payload)


async def _tail_file(info: dict, publish: Publisher, stop: asyncio.Event) -> None:
    path = Path(info["host_log_path"])
    offset = 0
    # Wait for the honeypot to create the log file.
    while not path.exists() and not stop.is_set():
        await asyncio.sleep(TAIL_POLL_INTERVAL)
    while not stop.is_set():
        try:
            size = path.stat().st_size
            if size < offset:  # rotated/truncated
                offset = 0
            if size > offset:
                with path.open("r") as fh:
                    fh.seek(offset)
                    new = fh.read()
                    offset = fh.tell()
                for line in new.splitlines():
                    await _emit_line(line, info["normalizer"], info["instance_id"], publish)
        except FileNotFoundError:
            offset = 0
        await asyncio.sleep(TAIL_POLL_INTERVAL)


async def _tail_stdout(info: dict, publish: Publisher, stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _reader() -> None:
        try:
            container = runner.client().containers.get(info["container_name"])
            for raw in container.logs(stream=True, follow=True, tail=0):
                loop.call_soon_threadsafe(queue.put_nowait, raw.decode("utf-8", "replace"))
        except Exception as err:  # noqa: BLE001 - container gone / restart
            logger.debug("stdout reader stopped for %s: %s", info["container_name"], err)

    reader_task = loop.run_in_executor(None, _reader)
    try:
        while not stop.is_set():
            try:
                line = await asyncio.wait_for(queue.get(), timeout=TAIL_POLL_INTERVAL)
            except asyncio.TimeoutError:
                continue
            await _emit_line(line, info["normalizer"], info["instance_id"], publish)
    finally:
        reader_task.cancel()


class TailerManager:
    """Tracks one tailer task per running instance."""

    def __init__(self, publish: Publisher) -> None:
        self._publish = publish
        self._tasks: dict[str, tuple[asyncio.Task, asyncio.Event]] = {}

    def start(self, info: dict) -> None:
        instance_id = info["instance_id"]
        self.stop(instance_id)
        stop = asyncio.Event()
        coro = _tail_file if info["mode"] == "file" else _tail_stdout
        task = asyncio.create_task(coro(info, self._publish, stop), name=f"tail-{instance_id}")
        self._tasks[instance_id] = (task, stop)
        logger.info("Started %s tailer for instance %s", info["mode"], instance_id)

    def stop(self, instance_id: str) -> None:
        existing = self._tasks.pop(instance_id, None)
        if existing:
            task, stop = existing
            stop.set()
            task.cancel()

    def stop_all(self) -> None:
        for instance_id in list(self._tasks):
            self.stop(instance_id)
