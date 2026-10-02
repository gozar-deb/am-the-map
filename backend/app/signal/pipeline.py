"""Chains the modular stages in signal/stages.py into a single pipeline that
keeps a small amount of per-sensor state (needed for temporal features and
outlier rejection across frames)."""
from __future__ import annotations

import numpy as np

from app.acquisition.base import CSIFrame
from app.signal import stages
from app.signal.stages import ProcessedCSI


class SignalProcessingPipeline:
    def __init__(self, noise_window: int = 3, subcarrier_keep_ratio: float = 0.8):
        self.noise_window = noise_window
        self.subcarrier_keep_ratio = subcarrier_keep_ratio
        self._prev_amplitude: dict[str, np.ndarray] = {}

    def process(self, frame: CSIFrame) -> ProcessedCSI:
        valid, reason = stages.validate_packet(frame)
        raw_amp = np.array(frame.subcarrier_amplitude, dtype=float)
        raw_phase = np.array(frame.subcarrier_phase, dtype=float)

        if not valid:
            return ProcessedCSI(
                sensor_id=frame.sensor_id,
                link_id=frame.link_id,
                timestamp=frame.timestamp,
                raw_amplitude=frame.subcarrier_amplitude,
                raw_phase=frame.subcarrier_phase,
                amplitude=raw_amp,
                phase=raw_phase,
                valid=False,
                reject_reason=reason,
            )

        amp = stages.reject_outliers(raw_amp)
        amp = stages.reduce_noise(amp, window=self.noise_window)
        amp = stages.normalize_amplitude(amp)
        phase = stages.sanitize_phase(raw_phase)
        amp, phase = stages.select_subcarriers(amp, phase, keep_ratio=self.subcarrier_keep_ratio)

        prev = self._prev_amplitude.get(frame.link_id)
        features = stages.extract_features(amp, phase, prev)
        self._prev_amplitude[frame.link_id] = amp

        return ProcessedCSI(
            sensor_id=frame.sensor_id,
            link_id=frame.link_id,
            timestamp=frame.timestamp,
            raw_amplitude=frame.subcarrier_amplitude,
            raw_phase=frame.subcarrier_phase,
            amplitude=amp,
            phase=phase,
            valid=True,
            features=features,
        )

    def reset(self) -> None:
        self._prev_amplitude.clear()
