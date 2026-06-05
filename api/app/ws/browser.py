"""Browser WebSocket endpoint for live events/jobs/hive status.

Auth: the SPA connects with ``/ws?token=<access_token>`` (browsers can't set
Authorization headers on WebSocket connections). The token is validated before
the connection is accepted.
"""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import ACCESS, decode_token
from app.ws.hub import hub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")) -> None:
    payload = decode_token(token)
    if payload is None or payload.get("type") != ACCESS:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception:  # noqa: BLE001
        await hub.disconnect(websocket)
