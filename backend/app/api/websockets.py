"""Live WebSocket streams (section 35).

When API_TOKEN is set, clients must connect with ?token=<token> (or send
X-API-Token / Authorization on the upgrade request).
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core import runtime
from app.core.auth import auth_enabled, _token_ok

router = APIRouter(tags=["websocket"])


def _credentials_ok(websocket: WebSocket, token: str | None) -> bool:
    if not auth_enabled():
        return True
    header_token = websocket.headers.get("x-api-token") or websocket.headers.get(
        "authorization"
    )
    if header_token and header_token.lower().startswith("bearer "):
        header_token = header_token[7:].strip()
    return _token_ok(token or header_token)


async def _pump_snapshots(ws: WebSocket, project) -> None:
    q = runtime.subscribe()
    try:
        while True:
            snapshot = await q.get()
            try:
                await ws.send_json(project(snapshot))
            except (WebSocketDisconnect, RuntimeError):
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    finally:
        runtime.unsubscribe(q)


async def _accept_or_reject(websocket: WebSocket, token: str | None) -> bool:
    """Accept the socket, then close with 4401 if auth fails.

    Closing *before* accept is undefined in many ASGI servers; accept-then-close
    is the portable rejection pattern.
    """
    await websocket.accept()
    if not _credentials_ok(websocket, token):
        await websocket.close(code=4401)
        return False
    return True


@router.websocket("/ws/map")
async def ws_map(websocket: WebSocket, token: str | None = Query(default=None)):
    if not await _accept_or_reject(websocket, token):
        return
    await _pump_snapshots(websocket, lambda s: s)


@router.websocket("/ws/sensors")
async def ws_sensors(websocket: WebSocket, token: str | None = Query(default=None)):
    if not await _accept_or_reject(websocket, token):
        return
    await _pump_snapshots(
        websocket,
        lambda s: {"sensors": s.get("sensors", []), "timestamp": s.get("timestamp")},
    )


@router.websocket("/ws/tracking")
async def ws_tracking(websocket: WebSocket, token: str | None = Query(default=None)):
    if not await _accept_or_reject(websocket, token):
        return
    await _pump_snapshots(
        websocket,
        lambda s: {"objects": s.get("objects", []), "timestamp": s.get("timestamp")},
    )


@router.websocket("/ws/csi")
async def ws_csi(websocket: WebSocket, token: str | None = Query(default=None)):
    if not await _accept_or_reject(websocket, token):
        return
    q = runtime.subscribe_csi()
    try:
        while True:
            preview = await q.get()
            try:
                await websocket.send_json(preview)
            except (WebSocketDisconnect, RuntimeError):
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    finally:
        runtime.unsubscribe_csi(q)
