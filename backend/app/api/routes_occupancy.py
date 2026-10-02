from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.runtime import engine
from app.database.models import Finding

router = APIRouter(prefix="/api/occupancy", tags=["occupancy"])


@router.get("")
async def current_occupancy():
    snap = engine.last_snapshot or {}
    env = snap.get("environment", {})
    return {
        "occupancy_count_estimate": env.get("occupancy_count_estimate", 0),
        "occupancy_probability": env.get("occupancy_probability", 0.0),
        "confidence": env.get("confidence", 0.0),
        "change_state": env.get("change_state", "NO_BASELINE"),
        "note": "Estimated by connected-component clustering of voxel occupancy "
        "probability above threshold -- not a validated head-count model.",
    }


@router.get("/history")
async def occupancy_history(limit: int = 50, db: Session = Depends(get_db)):
    """section 31/32 -- change-detection timeline, sourced from persisted findings."""
    limit = max(1, min(int(limit), 500))
    rows = db.query(Finding).order_by(Finding.created_at.desc()).limit(limit).all()
    return [
        {
            "id": f.id,
            "kind": f.kind,
            "description": f.description,
            "confidence": f.confidence,
            "created_at": f.created_at.isoformat(),
        }
        for f in rows
    ]
