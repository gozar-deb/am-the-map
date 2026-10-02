from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.runtime import engine
from app.database.models import Sensor
from app.schemas import SensorCreate, SensorPositionUpdate

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("")
async def list_sensors(db: Session = Depends(get_db)):
    """Merges persisted sensors (DB) with whatever the live acquisition
    adapter currently reports (e.g. the simulator's NODE-01/02/03, which are
    not pre-registered rows) so the list always reflects what's actually
    online, not just what was manually added via POST /api/sensors."""
    rows = {s.id: _serialize(s) for s in db.query(Sensor).all()}
    for sensor_id, live in engine.sensors.items():
        if sensor_id in rows:
            rows[sensor_id]["status"] = live.status
            rows[sensor_id]["csi_hz"] = live.csi_hz
            rows[sensor_id]["packet_loss_pct"] = live.packet_loss_pct
            rows[sensor_id]["latency_ms"] = live.latency_ms
            rows[sensor_id]["position"] = [live.x, live.y, live.z]
        else:
            rows[sensor_id] = {
                "id": sensor_id,
                "name": sensor_id,
                "hardware_type": "simulated" if engine.data_provenance.value == "simulated_data" else "unknown",
                "firmware": None,
                "position": [live.x, live.y, live.z],
                "orientation_deg": 0.0,
                "sampling_hz": None,
                "channel": None,
                "bandwidth_mhz": None,
                "antenna_config": None,
                "status": live.status,
                "csi_hz": live.csi_hz,
                "packet_loss_pct": live.packet_loss_pct,
                "latency_ms": live.latency_ms,
                "persisted": False,
            }
    return list(rows.values())


@router.post("")
async def create_sensor(payload: SensorCreate, db: Session = Depends(get_db)):
    existing = db.query(Sensor).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(400, f"Sensor '{payload.name}' already exists")
    sensor = Sensor(
        name=payload.name,
        hardware_type=payload.hardware_type,
        pos_x=payload.x,
        pos_y=payload.y,
        pos_z=payload.z,
        sampling_hz=payload.sampling_hz,
        channel=payload.channel,
        bandwidth_mhz=payload.bandwidth_mhz,
        status="offline",
    )
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    engine.set_sensor_positions({sensor.id: (sensor.pos_x, sensor.pos_y, sensor.pos_z)})
    return _serialize(sensor)


@router.get("/{sensor_id}")
async def get_sensor(sensor_id: str, db: Session = Depends(get_db)):
    sensor = db.query(Sensor).filter_by(id=sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    return _serialize(sensor)


@router.put("/{sensor_id}/position")
async def update_position(sensor_id: str, payload: SensorPositionUpdate, db: Session = Depends(get_db)):
    """Drag-and-drop sensor placement (section 10).

    Persisted sensors are updated in the DB; live-only sensors (e.g. simulator
    NODE-01) are updated in the mapping engine so the next snapshot keeps the
    new position instead of snapping back.
    """
    sensor = db.query(Sensor).filter_by(id=sensor_id).first()
    if sensor:
        sensor.pos_x, sensor.pos_y, sensor.pos_z = payload.x, payload.y, payload.z
        sensor.orientation_deg = payload.orientation_deg
        db.commit()
        engine.set_sensor_positions({sensor.id: (sensor.pos_x, sensor.pos_y, sensor.pos_z)})
        return _serialize(sensor)

    # Live adapter sensor not in DB
    if sensor_id in engine.sensors:
        engine.set_sensor_positions({sensor_id: (payload.x, payload.y, payload.z)})
        live = engine.sensors[sensor_id]
        return {
            "id": sensor_id,
            "name": sensor_id,
            "hardware_type": "live",
            "position": [live.x, live.y, live.z],
            "orientation_deg": payload.orientation_deg,
            "status": live.status,
            "csi_hz": live.csi_hz,
            "packet_loss_pct": live.packet_loss_pct,
            "latency_ms": live.latency_ms,
            "persisted": False,
        }
    raise HTTPException(404, "Sensor not found")


@router.delete("/{sensor_id}")
async def delete_sensor(sensor_id: str, db: Session = Depends(get_db)):
    sensor = db.query(Sensor).filter_by(id=sensor_id).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    db.delete(sensor)
    db.commit()
    return {"deleted": True}


def _serialize(s: Sensor) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "hardware_type": s.hardware_type,
        "firmware": s.firmware,
        "position": [s.pos_x, s.pos_y, s.pos_z],
        "orientation_deg": s.orientation_deg,
        "sampling_hz": s.sampling_hz,
        "channel": s.channel,
        "bandwidth_mhz": s.bandwidth_mhz,
        "antenna_config": s.antenna_config,
        "status": s.status,
        "csi_hz": None,
        "packet_loss_pct": s.packet_loss_pct,
        "latency_ms": s.latency_ms,
        "persisted": True,
    }
