from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.calibration.service import run_calibration
from app.core.runtime import engine, sensor_manager, start_pipeline
from app.database.models import CalibrationProfile
from app.schemas import CalibrationRequest

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.post("/run")
async def calibrate(payload: CalibrationRequest, db: Session = Depends(get_db)):
    """section 22 -- guided calibration workflow, steps 3-7. Steps 1-2
    (placing sensors / defining coordinates) happen via POST
    /api/sensors/{id}/position before calling this."""
    if not sensor_manager.running:
        await start_pipeline(mode="simulated")

    result = await run_calibration(engine, duration_s=payload.duration_s)
    if "error" in result:
        return result

    profile = CalibrationProfile(
        name=payload.name,
        signal_stability_pct=result["signal_stability_pct"],
        sensor_sync_pct=result["sensor_synchronization_pct"],
        packet_quality_pct=result["packet_quality_pct"],
        calibration_confidence_pct=result["calibration_confidence_pct"],
        baseline_snapshot=result["baseline_snapshot"],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    result["profile_id"] = profile.id
    return result


@router.get("/profiles")
async def list_profiles(db: Session = Depends(get_db)):
    rows = db.query(CalibrationProfile).order_by(CalibrationProfile.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "signal_stability_pct": p.signal_stability_pct,
            "sensor_sync_pct": p.sensor_sync_pct,
            "packet_quality_pct": p.packet_quality_pct,
            "calibration_confidence_pct": p.calibration_confidence_pct,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]


@router.post("/profiles/{profile_id}/apply")
async def apply_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(CalibrationProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(404, "profile not found")
    engine.apply_calibration_baseline(profile.baseline_snapshot or {})
    return {"applied": True, "profile_id": profile_id}
