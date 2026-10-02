from __future__ import annotations

from fastapi import APIRouter

from app.core.runtime import engine

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.get("")
async def current_tracks():
    """section 33 -- tracked candidate objects, anonymous IDs, no identity
    recognition claim."""
    snap = engine.last_snapshot or {}
    return {"objects": snap.get("objects", [])}


@router.get("/{object_id}")
async def get_track(object_id: str):
    snap = engine.last_snapshot or {}
    for obj in snap.get("objects", []):
        if obj["id"] == object_id:
            return obj
    return {"error": f"No active track '{object_id}'"}
