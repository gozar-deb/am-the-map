from __future__ import annotations

import time

from app.acquisition.base import CSIFrame, DataProvenance
from app.signal.pipeline import SignalProcessingPipeline


def _frame(amp=None, phase=None, seq=1):
    n = 32
    return CSIFrame(
        sensor_id="NODE-01",
        link_id="NODE-01<->AP",
        timestamp=time.time(),
        sequence=seq,
        subcarrier_amplitude=amp or [1.0] * n,
        subcarrier_phase=phase or [0.0] * n,
        rssi_dbm=-50.0,
        provenance=DataProvenance.SIMULATED_DATA,
    )


def test_valid_frame_processes():
    pipeline = SignalProcessingPipeline()
    result = pipeline.process(_frame())
    assert result.valid
    assert "energy" in result.features


def test_empty_frame_rejected():
    pipeline = SignalProcessingPipeline()
    frame = CSIFrame(
        sensor_id="NODE-01",
        link_id="NODE-01<->AP",
        timestamp=time.time(),
        sequence=1,
        subcarrier_amplitude=[],
        subcarrier_phase=[],
        rssi_dbm=-50.0,
        provenance=DataProvenance.SIMULATED_DATA,
    )
    result = pipeline.process(frame)
    assert not result.valid
    assert result.reject_reason == "empty_subcarrier_data"


def test_mismatched_lengths_rejected():
    pipeline = SignalProcessingPipeline()
    frame = _frame(amp=[1.0] * 32, phase=[0.0] * 16)
    result = pipeline.process(frame)
    assert not result.valid


def test_temporal_delta_accumulates_across_frames():
    pipeline = SignalProcessingPipeline()
    pipeline.process(_frame(amp=[1.0] * 32))
    result2 = pipeline.process(_frame(amp=[2.0] * 32, seq=2))
    assert result2.features["temporal_delta"] >= 0
