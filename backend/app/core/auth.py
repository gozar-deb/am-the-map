"""Optional API-token authentication.

When ``API_TOKEN`` is unset (default), the platform stays open for local
research use. When set, every HTTP request except health/docs must present
``Authorization: Bearer <token>`` or ``X-API-Token: <token>``.

WebSocket clients pass ``?token=<token>`` when auth is enabled.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, Query, Request, WebSocket

from app.core.config import settings


def auth_enabled() -> bool:
    return bool(settings.api_token)


def _token_ok(candidate: str | None) -> bool:
    if not settings.api_token:
        return True
    return bool(candidate) and candidate == settings.api_token


async def require_api_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> None:
    if not auth_enabled():
        return
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    token = x_api_token or bearer
    if not _token_ok(token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


async def require_ws_token(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Prefer the accept-then-close flow in api/websockets.py.

    This helper only validates credentials; callers must accept() first.
    """
    if not auth_enabled():
        return
    header_token = websocket.headers.get("x-api-token") or websocket.headers.get("authorization")
    if header_token and header_token.lower().startswith("bearer "):
        header_token = header_token[7:].strip()
    if not _token_ok(token or header_token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")
