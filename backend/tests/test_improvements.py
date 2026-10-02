"""Tests for v0.2 improvements: path safety, tracker prediction, calibration readiness."""
from __future__ import annotations

import pytest

from app.core.util import safe_resolve_dir, sanitize_id
from app.tracking.tracker import Tracker


def test_sanitize_id_rejects_traversal():
    with pytest.raises(ValueError):
        sanitize_id("../etc")
    with pytest.raises(ValueError):
        sanitize_id("a/b")
    assert sanitize_id("good-name") == "good-name"


def test_safe_resolve_dir_empty():
    with pytest.raises(ValueError):
        safe_resolve_dir("")


def test_tracker_predicts_and_matches():
    t = Tracker(max_match_distance_m=1.5)
    # First detection
    objs = t.update([{"x": 1.0, "y": 1.0, "z": 1.0, "confidence": 0.8}], dt=0.2)
    assert len(objs) == 1
    oid = objs[0].id
    # Move roughly consistent with velocity
    objs = t.update([{"x": 1.2, "y": 1.0, "z": 1.0, "confidence": 0.8}], dt=0.2)
    assert len(objs) == 1
    assert objs[0].id == oid
    assert objs[0].vx > 0
    # Coast when detection missing
    objs = t.update([], dt=0.2)
    assert len(objs) == 1
    assert objs[0].missed_ticks == 1


def test_tracker_ages_out():
    t = Tracker(max_missed_ticks=2)
    t.update([{"x": 0.0, "y": 0.0, "confidence": 0.5}], dt=0.2)
    t.update([], dt=0.2)
    t.update([], dt=0.2)
    objs = t.update([], dt=0.2)
    assert objs == []


def test_voxel_deposit_tiny_radius_no_crash():
    from app.mapping.voxel_grid import VoxelGrid

    g = VoxelGrid((5.0, 5.0, 3.0), 0.20)
    g.deposit((1.0, 1.0, 1.0), occupancy=0.5, movement=0.1, rf_intensity=0.2, confidence=0.5, radius_m=0.0)
    assert len(g.voxels) >= 1


def test_file_replay_finished_property():
    from app.acquisition.file_replay import FileReplayAdapter
    from pathlib import Path
    import tempfile, json

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "sensor_id": "S", "link_id": "L", "timestamp": 1.0, "sequence": 1,
            "subcarrier_amplitude": [1.0] * 8, "subcarrier_phase": [0.0] * 8,
            "rssi_dbm": -50,
        }) + "\n")
        path = f.name
    adapter = FileReplayAdapter(path, speed=100.0)
    import asyncio

    async def run():
        await adapter.start()
        assert adapter.finished is False
        # drain
        for _ in range(5):
            fr = await adapter.read_frame()
            if fr is None and adapter.finished:
                break
        assert adapter.finished is True
        await adapter.stop()

    asyncio.run(run())


def test_stale_features_pruned_when_sensor_offline():
    from app.mapping.engine import MappingEngine, SensorRuntimeInfo
    import time

    eng = MappingEngine()
    eng.sensors["NODE-01"] = SensorRuntimeInfo("NODE-01", 0, 0, 2)
    eng.sensors["NODE-01"].status = "online"
    eng.sensors["NODE-01"].last_seen = time.time()
    eng.link_to_sensor["NODE-01<->AP"] = "NODE-01"
    eng.latest_features["NODE-01<->AP"] = {
        "temporal_delta": 1.0,
        "amplitude_variance": 1.0,
        "phase_variance": 0.1,
        "energy": 1.0,
    }
    # Force offline via stale last_seen
    eng.sensors["NODE-01"].last_seen = time.time() - 10
    snap = eng.tick()
    assert "NODE-01<->AP" not in eng.latest_features
    assert snap["environment"]["occupancy_probability"] == 0.0


def test_reset_runtime_state_clears_grid():
    from app.mapping.engine import MappingEngine

    eng = MappingEngine()
    eng.grid.deposit((1, 1, 1), 0.9, 0.5, 0.5, 0.8)
    assert eng.grid.voxels
    eng.reset_runtime_state()
    assert not eng.grid.voxels
    assert eng.frame_count == 0
