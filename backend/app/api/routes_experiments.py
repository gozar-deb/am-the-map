from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import Experiment
from app.experiments import service
from app.schemas import ExperimentCreate

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("")
async def list_experiments(db: Session = Depends(get_db)):
    return [_serialize(e) for e in service.list_experiments(db)]


@router.post("")
async def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    exp = service.create_experiment(db, **payload.model_dump())
    return _serialize(exp)


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str, db: Session = Depends(get_db)):
    exp = service.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return _serialize(exp)


@router.delete("/{experiment_id}")
async def delete_experiment(experiment_id: str, db: Session = Depends(get_db)):
    if not service.delete_experiment(db, experiment_id):
        raise HTTPException(404, "Experiment not found")
    return {"deleted": True}


def _serialize(e: Experiment) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "hardware": e.hardware,
        "environment_desc": e.environment_desc,
        "sampling_hz": e.sampling_hz,
        "model_name": e.model_name,
        "duration_minutes": e.duration_minutes,
        "session_id": e.session_id,
        "notes": e.notes,
        "created_at": e.created_at.isoformat(),
    }
