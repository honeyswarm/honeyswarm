"""In-process pub/sub hub for pushing live updates to browser WebSockets.

Replaces the old DataTables AJAX polling. The ingest service publishes events
here; connected SPA clients receive them in real time.
"""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        logger.debug("WS client connected (%d total)", len(self._clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        logger.debug("WS client disconnected (%d total)", len(self._clients))

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        if not self._clients:
            return
        message = {"channel": channel, "data": data}
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop broken sockets
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


hub = WebSocketHub()
