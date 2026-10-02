"""Model registry (section 40). Tracks installed model metadata in the
database and exposes the single active spatial model instance.

Only the baseline heuristic model is runnable today (see baseline.py). It is
seeded into the registry on first run, marked `is_baseline=True` and
`validated=False` so `am-map models list` never misrepresents it."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import ModelRecord
from app.ml.baseline import BaselineHeuristicModel

_active_model = BaselineHeuristicModel()


def get_active_model() -> BaselineHeuristicModel:
    return _active_model


def ensure_seeded(db: Session) -> None:
    existing = db.query(ModelRecord).filter_by(name="baseline-heuristic-v1").first()
    if existing:
        return
    db.add(
        ModelRecord(
            name="baseline-heuristic-v1",
            version="0.1.0",
            task="occupancy",
            architecture="baseline-heuristic",
            input_format="csi-features (energy, amplitude_variance, phase_variance, temporal_delta)",
            output_format="occupancy_probability, movement_probability, coarse position, confidence",
            training_dataset=None,
            hardware_requirements="CPU",
            accuracy_metrics={},
            license="Apache-2.0 (project default)",
            validated=False,
            is_baseline=True,
        )
    )
    db.commit()


def list_models(db: Session) -> list[ModelRecord]:
    return db.query(ModelRecord).all()


def get_model_info(db: Session, name: str) -> ModelRecord | None:
    return db.query(ModelRecord).filter_by(name=name).first()
