"""
The runtime glue: two background asyncio tasks once acquisition is started --

  1. an ingest loop pulling CSIFrames from the active SensorManager adapter
     and feeding them into the MappingEngine (and, if a session is being
     recorded, appending them to disk in FileReplayAdapter's format so
     `am-map replay` can play them back exactly, section 30)
  2. a tick loop that calls MappingEngine.tick() at a fixed rate and fans the
     resulting snapshot out to every subscribed WebSocket connection
     (section 24 -- dynamic, continuously updating map)
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from pathlib import Path
from typing import Optional

from app.acquisition.base import CSIFrame
from app.acquisition.manager import sensor_manager
from app.core.config import settings
from app.core.logging import get_logger
from app.core.util import sanitize_id
from app.mapping.engine import MappingEngine

logger = get_logger("core.runtime")

engine = MappingEngine(bounds_m=settings.room_bounds_m, resolution_m=settings.voxel_resolution_m)

_subscribers: set[asyncio.Queue] = set()      # map/tick-rate snapshots (/ws/map, /ws/sensors, /ws/tracking)
_csi_subscribers: set[asyncio.Queue] = set()  # per-frame processed CSI (/ws/csi, section 14)
_ingest_task: Optional[asyncio.Task] = None
_tick_task: Optional[asyncio.Task] = None

_recording_file = None
_recording_session_id: str | None = None
_frame_count_this_session = 0


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def subscribe_csi() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _csi_subscribers.add(q)
    return q


def unsubscribe_csi(q: asyncio.Queue) -> None:
    _csi_subscribers.discard(q)


def _fanout(subscribers: set[asyncio.Queue], payload: dict) -> None:
    for q in list(subscribers):
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def _broadcast(snapshot: dict) -> None:
    _fanout(_subscribers, snapshot)


def _broadcast_csi(preview: dict) -> None:
    _fanout(_csi_subscribers, preview)


def start_recording(session_id: str) -> Path:
    global _recording_file, _recording_session_id, _frame_count_this_session
    session_id = sanitize_id(session_id, "session_id")
    path = settings.data_dir / "recordings" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _recording_file = open(path, "w")
    _recording_session_id = session_id
    _frame_count_this_session = 0
    logger.info("recording.started", session_id=session_id, path=str(path))
    return path


def stop_recording() -> int:
    global _recording_file, _recording_session_id
    count = _frame_count_this_session
    if _recording_file:
        _recording_file.close()
    _recording_file = None
    _recording_session_id = None
    logger.info("recording.stopped", frame_count=count)
    return count


def is_recording() -> bool:
    return _recording_file is not None


def _record_frame(frame: CSIFrame) -> None:
    global _frame_count_this_session
    if _recording_file is None:
        return
    row = dataclasses.asdict(frame)
    row["provenance"] = frame.provenance.value
    # Enums / non-JSON types already normalized; ensure debug field is plain
    if row.get("debug_ground_truth") is not None and not isinstance(
        row["debug_ground_truth"], (dict, list, str, int, float, bool, type(None))
    ):
        row["debug_ground_truth"] = str(row["debug_ground_truth"])
    try:
        _recording_file.write(json.dumps(row) + "\n")
        _recording_file.flush()
    except (TypeError, ValueError) as e:
        logger.info("recording.serialize_failed", error=str(e))
        return
    _frame_count_this_session += 1


async def _ingest_loop() -> None:
    try:
        async for frame in sensor_manager.frames():
            try:
                preview = engine.ingest(frame)
                if preview is not None:
                    _broadcast_csi(preview)
                _record_frame(frame)
            except Exception as e:
                # One bad frame must not kill the whole acquisition session
                logger.info("ingest_loop.frame_error", error=str(e))
                continue
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.info("ingest_loop.crashed", error=str(e))
        return


_last_logged_change_state = "UNCHANGED"


def _maybe_log_finding(snapshot: dict) -> None:
    """section 23/32 change detection -> persisted Finding rows so the
    timeline/history endpoints have something to show."""
    global _last_logged_change_state
    from app.database.db import db_session  # local import: avoid import cycle at module load
    from app.database.models import Finding

    state = snapshot["environment"]["change_state"]
    if state in ("UNCHANGED", "NO_BASELINE") or state == _last_logged_change_state:
        _last_logged_change_state = state
        return
    _last_logged_change_state = state
    with db_session() as db:
        db.add(
            Finding(
                kind=state.lower(),
                description=f"Change state transitioned to {state}",
                confidence=snapshot["environment"]["confidence"],
                data={"environment": snapshot["environment"]},
            )
        )


async def _tick_loop(interval_s: float = 0.2) -> None:
    try:
        while True:
            await asyncio.sleep(interval_s)
            if not sensor_manager.running:
                continue
            # Keep packet_loss / latency from the live adapter visible in snapshots
            try:
                engine.sync_adapter_health(sensor_manager.health())
            except Exception:
                pass
            snapshot = engine.tick()
            _maybe_log_finding(snapshot)
            _broadcast(snapshot)
    except asyncio.CancelledError:
        return


async def start_pipeline(mode: str = "simulated", **adapter_kwargs) -> None:
    global _ingest_task, _tick_task
    # Switching modes must not leave the previous mode's voxels/tracks/features
    engine.reset_runtime_state()
    await sensor_manager.start(mode, **adapter_kwargs)
    if mode == "simulated":
        # seed sensor topology immediately so the UI has positions before
        # the first frames arrive
        adapter = sensor_manager.adapter
        positions = {s.sensor_id: (s.x, s.y, s.z) for s in getattr(adapter, "sensors", [])}
        engine.set_sensor_positions(positions)
    if _ingest_task is None or _ingest_task.done():
        _ingest_task = asyncio.create_task(_ingest_loop())
    if _tick_task is None or _tick_task.done():
        _tick_task = asyncio.create_task(_tick_loop())


async def stop_pipeline() -> None:
    global _ingest_task, _tick_task
    await sensor_manager.stop()
    tasks = [_ingest_task, _tick_task]
    _ingest_task = None
    _tick_task = None
    for task in tasks:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
    if is_recording():
        stop_recording()
