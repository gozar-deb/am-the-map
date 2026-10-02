"""Unit tests for live CSI parsers and adapter wiring (no hardware required)."""
from __future__ import annotations

import json
import math

from app.acquisition.esp32 import parse_csi_payload
from app.acquisition.base import DataProvenance


def test_parse_json_amplitude_phase():
    line = json.dumps(
        {
            "sensor_id": "NODE-A",
            "amplitude": [1.0, 1.5, 2.0, 1.2],
            "phase": [0.1, -0.2, 0.0, 0.3],
            "rssi": -45,
            "seq": 7,
        }
    )
    frame = parse_csi_payload(line)
    assert frame is not None
    assert frame.sensor_id == "NODE-A"
    assert frame.subcarrier_amplitude == [1.0, 1.5, 2.0, 1.2]
    assert frame.rssi_dbm == -45.0
    assert frame.sequence == 7
    assert frame.provenance == DataProvenance.REAL_SENSOR_DATA


def test_parse_json_complex_csi():
    # flat IQ pairs
    csi = []
    for i in range(8):
        csi.extend([1.0, 0.0])  # amplitude 1, phase 0
    line = json.dumps({"csi": csi, "rssi": -50})
    frame = parse_csi_payload(line, default_sensor_id="X")
    assert frame is not None
    assert len(frame.subcarrier_amplitude) == 8
    assert all(abs(a - 1.0) < 1e-6 for a in frame.subcarrier_amplitude)
    assert all(abs(p) < 1e-6 for p in frame.subcarrier_phase)


def test_parse_amp_phase_pipe():
    line = "1.0 2.0 3.0 | 0.1 0.2 0.3"
    frame = parse_csi_payload(line, default_sensor_id="PIPE")
    assert frame is not None
    assert frame.subcarrier_amplitude == [1.0, 2.0, 3.0]
    assert frame.subcarrier_phase == [0.1, 0.2, 0.3]


def test_parse_rejects_garbage():
    assert parse_csi_payload("hello world") is None
    assert parse_csi_payload("") is None
    assert parse_csi_payload("# comment") is None


def test_adapter_registry_has_live_modes():
    from app.acquisition.manager import ADAPTER_REGISTRY

    assert "esp32" in ADAPTER_REGISTRY
    assert "linux_csi" in ADAPTER_REGISTRY
    assert ADAPTER_REGISTRY["esp32"].provenance == DataProvenance.REAL_SENSOR_DATA
    assert ADAPTER_REGISTRY["linux_csi"].provenance == DataProvenance.REAL_SENSOR_DATA
