"""status / doctor / config / scan / pipeline control (sections 4, 38, 45)."""
from __future__ import annotations

import importlib.util
import platform

from fastapi import APIRouter, HTTPException

from app.acquisition.file_replay import FileReplayAdapter
from app.acquisition.manager import sensor_manager
from app.core import runtime
from app.core.config import settings
from app.core.util import sanitize_id
from app.database.db import db_session
from app.database.models import Sensor
from app.schemas import PipelineStartRequest

router = APIRouter(tags=["system"])


@router.get("/api/status")
async def status():
    snap = runtime.engine.last_snapshot
    return {
        "app": settings.app_name,
        "environment": settings.environment,
        "acquisition_mode": sensor_manager.mode,
        "acquisition_running": sensor_manager.running,
        "recording": runtime.is_recording(),
        "ai_mode": settings.ai_mode.value,
        "privacy_mode": settings.privacy_mode,
        "map": snap or {"note": "pipeline not started -- POST /api/system/start"},
    }


@router.get("/api/system/doctor")
async def doctor():
    def _has(mod: str) -> bool:
        return importlib.util.find_spec(mod) is not None

    torch_ok = _has("torch")
    cuda_available = False
    if torch_ok:
        try:
            import torch  # noqa: PLC0415

            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            cuda_available = False

    # Probe database
    db_ok = False
    try:
        with db_session() as db:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    health = sensor_manager.health()
    online = sum(1 for h in health if h.status == "online")
    model = runtime.engine.model if hasattr(runtime, "engine") else None
    snap = runtime.engine.last_snapshot if hasattr(runtime, "engine") else None
    calibrated = bool(getattr(runtime.engine, "baseline_snapshot", None))

    checks = {
        "python": platform.python_version(),
        "app_version": "0.2.4",
        "dependencies": {
            "fastapi": _has("fastapi"),
            "sqlalchemy": _has("sqlalchemy"),
            "numpy": _has("numpy"),
            "torch": torch_ok,
            "onnxruntime": _has("onnxruntime"),
            "pyserial": _has("serial"),
        },
        "database": db_ok,
        "websocket": True,
        "gpu_detected": cuda_available,
        "cuda_available": cuda_available,
        "acquisition_mode": sensor_manager.mode,
        "acquisition_running": sensor_manager.running,
        "sensors_online": online,
        "sensors_total": len(health),
        "csi_stream_active": sensor_manager.running and online > 0,
        "model_loaded": model is not None,
        "model_name": getattr(model, "name", None),
        "model_validated": bool(getattr(model, "validated", False)),
        "calibrated": calibrated,
        "frame_count": (snap or {}).get("frame_count", 0) if isinstance(snap, dict) else 0,
        "auth_enabled": bool(settings.api_token),
        "ai_configuration": {
            "ai_mode": settings.ai_mode.value,
            "privacy_mode": settings.privacy_mode,
            "any_cloud_key_configured": settings.any_cloud_key_configured(),
        },
        "inference_mode": "CPU" if not cuda_available else "GPU (CUDA)",
        "training_recommendation": (
            "External GPU recommended for training" if not cuda_available else "Local GPU available"
        ),
        "ready_for_live": sensor_manager.running and online >= 1,
        "localization_ready": online >= 3,
    }
    return checks


@router.get("/api/system/config")
async def get_config():
    return {
        "ai_mode": settings.ai_mode.value,
        "privacy_mode": settings.privacy_mode,
        "voxel_resolution_m": settings.voxel_resolution_m,
        "room_bounds_m": settings.room_bounds_m,
        "default_sampling_hz": settings.default_sampling_hz,
    }


@router.get("/api/system/scan")
async def scan():
    """section 4 -- `am-map scan`: list registered sensors and live adapter health.
    Live health reflects the active acquisition mode (simulator, esp32, linux_csi, replay)."""
    with db_session() as db:
        known = db.query(Sensor).all()
        known_out = [{"id": s.id, "name": s.name, "hardware_type": s.hardware_type, "status": s.status} for s in known]
    live = [{"id": h.sensor_id, "status": h.status} for h in sensor_manager.health()]
    return {"known_sensors": known_out, "live_health": live}


@router.post("/api/system/start")
async def start_pipeline(req: PipelineStartRequest):
    kwargs = {}
    if req.mode == "file_replay":
        if not req.replay_session_id:
            return {"error": "replay_session_id is required for file_replay mode"}
        try:
            safe_session_id = sanitize_id(req.replay_session_id, "replay_session_id")
        except ValueError as e:
            raise HTTPException(400, str(e))
        path = settings.data_dir / "recordings" / f"{safe_session_id}.jsonl"
        kwargs = {"recording_path": str(path), "speed": req.replay_speed}
    elif req.mode in ("esp32", "linux_csi"):
        # Pass through live-hardware connection parameters
        for key in (
            "port", "baud", "udp_host", "udp_port",
            "tcp_host", "tcp_port", "source_path", "sensor_id", "interface",
        ):
            val = getattr(req, key, None)
            if val is not None:
                kwargs[key] = val
    try:
        await runtime.start_pipeline(mode=req.mode, **kwargs)
    except Exception as e:
        raise HTTPException(400, f"Failed to start acquisition mode '{req.mode}': {e}")
    if req.recording_name:
        try:
            safe_recording_name = sanitize_id(req.recording_name, "recording_name")
        except ValueError as e:
            raise HTTPException(400, str(e))
        runtime.start_recording(safe_recording_name)
    return {"started": True, "mode": req.mode, "recording": runtime.is_recording()}


@router.post("/api/system/stop")
async def stop_pipeline():
    await runtime.stop_pipeline()
    return {"stopped": True}
