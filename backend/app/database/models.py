"""ORM models -- section 36 (Database)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String, unique=True)
    mac_address: Mapped[str | None] = mapped_column(String, nullable=True)
    hardware_type: Mapped[str] = mapped_column(String, default="simulated")  # esp32, esp32-s3, linux-csi, simulated
    firmware: Mapped[str | None] = mapped_column(String, nullable=True)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    pos_z: Mapped[float] = mapped_column(Float, default=2.0)
    orientation_deg: Mapped[float] = mapped_column(Float, default=0.0)
    sampling_hz: Mapped[float] = mapped_column(Float, default=20.0)
    channel: Mapped[int] = mapped_column(Integer, default=6)
    bandwidth_mhz: Mapped[int] = mapped_column(Integer, default=20)
    antenna_config: Mapped[str] = mapped_column(String, default="1x1")
    status: Mapped[str] = mapped_column(String, default="offline")  # online, offline, degraded
    packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Session_(Base):
    """A recording session (section 30)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="idle")  # idle, recording, stopped, replaying
    source: Mapped[str] = mapped_column(String, default="simulated")  # simulated | real | replay
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    recording_path: Mapped[str | None] = mapped_column(String, nullable=True)
    session_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Experiment(Base):
    """section 29."""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String)
    hardware: Mapped[str | None] = mapped_column(String, nullable=True)
    environment_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    sampling_hz: Mapped[float] = mapped_column(Float, default=20.0)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, ForeignKey("sessions.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CalibrationProfile(Base):
    """section 22."""

    __tablename__ = "calibration_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String)
    signal_stability_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sensor_sync_pct: Mapped[float] = mapped_column(Float, default=0.0)
    packet_quality_pct: Mapped[float] = mapped_column(Float, default=0.0)
    calibration_confidence_pct: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelRecord(Base):
    """section 40 -- installed / registered model metadata."""

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String, unique=True)
    version: Mapped[str] = mapped_column(String, default="0.1.0")
    task: Mapped[str] = mapped_column(String)  # occupancy | localization | tracking | pose
    architecture: Mapped[str] = mapped_column(String, default="baseline-heuristic")
    input_format: Mapped[str] = mapped_column(String, default="csi-features")
    output_format: Mapped[str] = mapped_column(String, default="voxel-probabilities")
    training_dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    hardware_requirements: Mapped[str] = mapped_column(String, default="CPU")
    accuracy_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    license: Mapped[str] = mapped_column(String, default="N/A")
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Finding(Base):
    """Observations / change-detection findings (sections 23, 32)."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    session_id: Mapped[str | None] = mapped_column(String, ForeignKey("sessions.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String)  # new_occupancy | movement | changed_region | low_confidence
    description: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIRequest(Base):
    """section 20/21 -- log of AI gateway requests (never raw CSI unless opted in)."""

    __tablename__ = "ai_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    provider: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_call_made: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserSetting(Base):
    __tablename__ = "user_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
