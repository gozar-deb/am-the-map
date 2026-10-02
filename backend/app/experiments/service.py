"""Experiment management (section 29). Every experiment is stored
reproducibly: hardware, environment, sampling rate, model, duration, and a
link back to the recorded session that produced it."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Experiment


def create_experiment(
    db: Session,
    name: str,
    hardware: str | None = None,
    environment_desc: str | None = None,
    sampling_hz: float = 20.0,
    model_name: str | None = None,
    duration_minutes: float | None = None,
    session_id: str | None = None,
    notes: str | None = None,
) -> Experiment:
    exp = Experiment(
        name=name,
        hardware=hardware,
        environment_desc=environment_desc,
        sampling_hz=sampling_hz,
        model_name=model_name,
        duration_minutes=duration_minutes,
        session_id=session_id,
        notes=notes,
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def list_experiments(db: Session) -> list[Experiment]:
    return db.query(Experiment).order_by(Experiment.created_at.desc()).all()


def get_experiment(db: Session, experiment_id: str) -> Experiment | None:
    return db.query(Experiment).filter_by(id=experiment_id).first()


def delete_experiment(db: Session, experiment_id: str) -> bool:
    exp = get_experiment(db, experiment_id)
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True
