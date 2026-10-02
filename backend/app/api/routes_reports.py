"""Report generation (section 47). Builds a report from the live/last map
snapshot plus optional experiment/calibration context. Markdown and JSON are
always available; HTML wraps the markdown; PDF uses ReportLab if installed."""
from __future__ import annotations

import io
import json
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.runtime import engine
from app.database.models import CalibrationProfile, Experiment
from app.schemas import ReportRequest

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _build_report_dict(db: Session, req: ReportRequest) -> dict:
    snap = engine.last_snapshot or {}
    env = snap.get("environment", {})

    experiment = None
    if req.experiment_id:
        exp = db.query(Experiment).filter_by(id=req.experiment_id).first()
        if exp:
            experiment = {
                "name": exp.name,
                "hardware": exp.hardware,
                "environment_desc": exp.environment_desc,
                "sampling_hz": exp.sampling_hz,
                "model_name": exp.model_name,
                "duration_minutes": exp.duration_minutes,
                "notes": exp.notes,
            }

    calibration = None
    latest_cal = db.query(CalibrationProfile).order_by(CalibrationProfile.created_at.desc()).first()
    if latest_cal:
        calibration = {
            "name": latest_cal.name,
            "signal_stability_pct": latest_cal.signal_stability_pct,
            "sensor_sync_pct": latest_cal.sensor_sync_pct,
            "packet_quality_pct": latest_cal.packet_quality_pct,
            "calibration_confidence_pct": latest_cal.calibration_confidence_pct,
        }

    return {
        "generated_at": time.time(),
        "experiment_summary": experiment,
        "hardware": [s["id"] for s in snap.get("sensors", [])],
        "sensor_placement": snap.get("sensors", []),
        "environment": env,
        "calibration": calibration,
        "model": {
            "name": env.get("model"),
            "is_baseline": bool(env.get("model_is_baseline", True)),
            "validated": bool(env.get("model_validated", False)),
        },
        "measurements": {
            "frame_count": snap.get("frame_count", 0),
            "rejected_count": snap.get("rejected_count", 0),
            "avg_csi_hz": env.get("avg_csi_hz"),
        },
        "map_summary": {
            "voxel_count_active": len(snap.get("voxels", [])),
            "bounds_m": env.get("bounds_m"),
            "resolution_m": env.get("voxel_resolution_m"),
        },
        "occupancy": {
            "count_estimate": env.get("occupancy_count_estimate"),
            "probability": env.get("occupancy_probability"),
        },
        "tracking": snap.get("objects", []),
        "changes": env.get("change_state"),
        "confidence": env.get("confidence"),
        "limitations": [
            "This platform infers spatial information from WiFi CSI, not "
            "camera or LiDAR data -- it does not provide pixel-level imagery.",
            "The active model is an unvalidated baseline heuristic, not a "
            "trained/evaluated learned model.",
            "Position estimates use activity-weighted sensor centroids, not "
            "true multilateration, and are unreliable with fewer than 3 "
            "active sensors.",
            "Occupancy counts come from connected-component clustering of "
            "voxel activity and can over- or under-count close-together "
            "objects.",
        ],
    }


def _to_markdown(report: dict) -> str:
    lines = [f"# Am the Map -- Experiment Report", "", f"_Generated: {time.ctime(report['generated_at'])}_", ""]

    def section(title: str, body):
        lines.append(f"## {title}")
        if isinstance(body, (dict, list)):
            lines.append("```json")
            lines.append(json.dumps(body, indent=2, default=str))
            lines.append("```")
        else:
            lines.append(str(body))
        lines.append("")

    section("Experiment Summary", report["experiment_summary"] or "No experiment linked.")
    section("Hardware", report["hardware"])
    section("Sensor Placement", report["sensor_placement"])
    section("Environment", report["environment"])
    section("Calibration", report["calibration"] or "No calibration profile recorded.")
    section("Model", report["model"])
    section("Measurements", report["measurements"])
    section("3D Map Summary", report["map_summary"])
    section("Occupancy", report["occupancy"])
    section("Tracking", report["tracking"])
    section("Changes", report["changes"])
    section("Confidence", report["confidence"])
    lines.append("## Limitations")
    for item in report["limitations"]:
        lines.append(f"- {item}")
    return "\n".join(lines)


@router.post("")
async def generate_report(req: ReportRequest, db: Session = Depends(get_db)):
    report = _build_report_dict(db, req)

    if req.format == "json":
        return report

    markdown = _to_markdown(report)

    if req.format == "markdown":
        return Response(content=markdown, media_type="text/markdown")

    if req.format == "html":
        html = "<html><body><pre style='font-family:ui-monospace'>" + markdown.replace("<", "&lt;") + "</pre></body></html>"
        return Response(content=html, media_type="text/html")

    if req.format == "pdf":
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Preformatted
        except ImportError:
            return Response(
                content="PDF export requires the 'reportlab' package (pip install reportlab).",
                media_type="text/plain",
                status_code=501,
            )
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=LETTER)
        styles = getSampleStyleSheet()
        story = [Paragraph("Am the Map -- Experiment Report", styles["Title"]), Spacer(1, 12)]
        for block in markdown.split("\n\n"):
            story.append(Preformatted(block, styles["Code"]))
            story.append(Spacer(1, 8))
        doc.build(story)
        return Response(content=buf.getvalue(), media_type="application/pdf")

    return {"error": f"Unknown format '{req.format}'. Use markdown | json | html | pdf."}
