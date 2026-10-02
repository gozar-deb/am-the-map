from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core import runtime
from app.database.models import Session_
from app.schemas import SessionCreate

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(db: Session = Depends(get_db)):
    rows = db.query(Session_).order_by(Session_.created_at.desc()).all()
    return [_serialize(s) for s in rows]


@router.post("/record")
async def start_recording(payload: SessionCreate, db: Session = Depends(get_db)):
    """section 30 -- `am-map record`."""
    session = Session_(name=payload.name, status="recording", source=payload.source, started_at=datetime.utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)

    # Only auto-start the simulator if nothing is running. Hardware modes
    # (esp32 / linux_csi) require connection params — start those via
    # POST /api/system/start first, then record.
    if not runtime.sensor_manager.running:
        mode = payload.source if payload.source in ("simulated", "file_replay") else "simulated"
        if mode == "simulated":
            await runtime.start_pipeline(mode="simulated")
        else:
            raise HTTPException(
                400,
                f"Acquisition is stopped. Start mode '{payload.source}' via "
                "POST /api/system/start (with hardware params if needed) before recording.",
            )
    runtime.start_recording(session.id)
    return _serialize(session)


@router.post("/{session_id}/stop")
async def stop_recording(session_id: str, db: Session = Depends(get_db)):
    session = db.query(Session_).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    frame_count = runtime.stop_recording()
    session.status = "stopped"
    session.ended_at = datetime.utcnow()
    session.frame_count = frame_count
    session.recording_path = str(runtime.settings.data_dir / "recordings" / f"{session_id}.jsonl")
    db.commit()
    return _serialize(session)


@router.post("/{session_id}/replay")
async def replay_session(session_id: str, speed: float = 1.0, db: Session = Depends(get_db)):
    """section 30 -- `am-map replay <session>`. Reproduces the original
    visualization/inference timeline by feeding the recorded frames back
    through the exact same signal->ML->mapping pipeline."""
    session = db.query(Session_).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    path = runtime.settings.data_dir / "recordings" / f"{session_id}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"No recording file for session {session_id}")

    await runtime.start_pipeline(mode="file_replay", recording_path=str(path), speed=speed)
    session.status = "replaying"
    db.commit()
    return {"replaying": True, "session_id": session_id, "path": str(path)}


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(Session_).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    path = runtime.settings.data_dir / "recordings" / f"{session_id}.jsonl"
    if path.exists():
        path.unlink()
    db.delete(session)
    db.commit()
    return {"deleted": True}


def _serialize(s: Session_) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "status": s.status,
        "source": s.source,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "frame_count": s.frame_count,
        "recording_path": s.recording_path,
    }
