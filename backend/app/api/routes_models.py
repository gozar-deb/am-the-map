from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import ModelRecord
from app.ml.registry import ensure_seeded, get_active_model, get_model_info, list_models

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_all(db: Session = Depends(get_db)):
    """section 40 -- `am-map models list`."""
    ensure_seeded(db)
    rows = list_models(db)
    return [_serialize(m) for m in rows]


@router.get("/active")
async def active_model():
    m = get_active_model()
    return {"name": m.name, "architecture": m.architecture.value, "validated": m.validated, "is_baseline": True}


@router.get("/{name}")
async def model_info(name: str, db: Session = Depends(get_db)):
    ensure_seeded(db)
    row = get_model_info(db, name)
    if not row:
        raise HTTPException(404, f"No model named '{name}'")
    return _serialize(row)


@router.post("/{name}/install")
async def install_model(name: str):
    """section 40 -- `am-map models install`. Only the bundled baseline is
    runnable today; installing a real trained checkpoint is a manual step
    (see docs/ml.md) until a model hub is wired up."""
    return {
        "installed": False,
        "message": f"No downloadable checkpoint registered for '{name}' yet. "
        "Train one with `am-map train` or drop a checkpoint into models/<task>/ "
        "and register it -- see docs/ml.md.",
    }


@router.delete("/{name}")
async def remove_model(name: str, db: Session = Depends(get_db)):
    # Without this, deleting "baseline-heuristic-v1" on a freshly created
    # database (before anything ever called GET /api/models to seed it)
    # would 404 instead of correctly reporting "protected baseline model" --
    # same end result (nothing gets deleted) but a misleading error.
    ensure_seeded(db)
    row = get_model_info(db, name)
    if not row:
        raise HTTPException(404, f"No model named '{name}'")
    if row.is_baseline:
        raise HTTPException(400, "Cannot remove the bundled baseline model")
    db.delete(row)
    db.commit()
    return {"deleted": True}


def _serialize(m: ModelRecord) -> dict:
    return {
        "name": m.name,
        "version": m.version,
        "task": m.task,
        "architecture": m.architecture,
        "input_format": m.input_format,
        "output_format": m.output_format,
        "training_dataset": m.training_dataset,
        "hardware_requirements": m.hardware_requirements,
        "accuracy_metrics": m.accuracy_metrics,
        "license": m.license,
        "validated": m.validated,
        "is_baseline": m.is_baseline,
    }
