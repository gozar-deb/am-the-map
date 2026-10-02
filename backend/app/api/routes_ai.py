from __future__ import annotations

import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.gateway import ai_gateway
from app.api.deps import get_db
from app.core.config import settings
from app.core.runtime import engine
from app.schemas import AIAskRequest

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Simple in-process sliding-window rate limit for /ask
_ask_timestamps: deque[float] = deque(maxlen=500)


def _check_rate_limit() -> None:
    limit = max(1, settings.ai_rate_limit_per_minute)
    now = time.time()
    while _ask_timestamps and now - _ask_timestamps[0] > 60.0:
        _ask_timestamps.popleft()
    if len(_ask_timestamps) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"AI rate limit exceeded ({limit} requests/minute). Try again shortly.",
        )
    _ask_timestamps.append(now)


@router.get("/status")
async def ai_status():
    """section 19 -- current operating mode, always visible."""
    return ai_gateway.status()


@router.post("/ask")
async def ask(payload: AIAskRequest, db: Session = Depends(get_db)):
    """section 20 -- ask an optional LLM about the current map."""
    _check_rate_limit()
    snapshot = engine.last_snapshot or {
        "environment": {},
        "sensors": [],
        "objects": [],
        "provenance": "none",
    }
    raw_features = engine.latest_features if payload.include_raw_features else None
    return await ai_gateway.ask(
        db,
        question=payload.question,
        snapshot=snapshot,
        provider_name=payload.provider,
        include_raw_features=payload.include_raw_features,
        raw_features=raw_features,
    )
