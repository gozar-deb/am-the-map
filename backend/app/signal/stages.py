"""
Modular CSI signal-processing stages (sections 12-13):

    Raw CSI -> validation -> timestamp sync -> outlier detection ->
    noise reduction -> amplitude normalization -> phase processing ->
    subcarrier processing -> feature extraction

Each stage is a small pure function so it can be tested, reordered, or
swapped independently, and so raw vs. processed CSI can both be inspected
(section 13).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.acquisition.base import CSIFrame


@dataclass
class ProcessedCSI:
    sensor_id: str
    link_id: str
    timestamp: float
    raw_amplitude: list[float]
    raw_phase: list[float]
    amplitude: np.ndarray
    phase: np.ndarray
    valid: bool = True
    reject_reason: str | None = None
    features: dict = field(default_factory=dict)


def validate_packet(frame: CSIFrame) -> tuple[bool, str | None]:
    if not frame.subcarrier_amplitude or not frame.subcarrier_phase:
        return False, "empty_subcarrier_data"
    if len(frame.subcarrier_amplitude) != len(frame.subcarrier_phase):
        return False, "amplitude_phase_length_mismatch"
    if any(np.isnan(v) or np.isinf(v) for v in frame.subcarrier_amplitude):
        return False, "nan_or_inf_amplitude"
    return True, None


def reject_outliers(amplitude: np.ndarray, z_thresh: float = 4.0) -> np.ndarray:
    """Clip subcarriers whose amplitude deviates too far from the local mean."""
    mean, std = amplitude.mean(), amplitude.std() + 1e-9
    z = np.abs((amplitude - mean) / std)
    cleaned = amplitude.copy()
    cleaned[z > z_thresh] = mean
    return cleaned


def reduce_noise(amplitude: np.ndarray, window: int = 3) -> np.ndarray:
    """Simple moving-average smoothing across subcarriers."""
    if window <= 1 or len(amplitude) < window:
        return amplitude
    kernel = np.ones(window) / window
    return np.convolve(amplitude, kernel, mode="same")


def normalize_amplitude(amplitude: np.ndarray) -> np.ndarray:
    lo, hi = amplitude.min(), amplitude.max()
    if hi - lo < 1e-9:
        return np.zeros_like(amplitude)
    return (amplitude - lo) / (hi - lo)


def sanitize_phase(phase: np.ndarray) -> np.ndarray:
    """Unwrap phase to remove artificial 2*pi discontinuities."""
    return np.unwrap(phase)


def select_subcarriers(amplitude: np.ndarray, phase: np.ndarray, keep_ratio: float = 0.8):
    """Drop the noisiest edge subcarriers, keep the central `keep_ratio` band."""
    n = len(amplitude)
    drop = int(n * (1 - keep_ratio) / 2)
    if drop <= 0:
        return amplitude, phase
    return amplitude[drop:n - drop], phase[drop:n - drop]


def extract_features(amplitude: np.ndarray, phase: np.ndarray, prev_amplitude: np.ndarray | None) -> dict:
    """Hand-crafted features used by the baseline spatial ML model.

    These are intentionally simple (energy / variance / temporal delta)
    rather than learned embeddings -- see ml/baseline.py for why.
    """
    energy = float(np.mean(amplitude ** 2))
    variance = float(np.var(amplitude))
    phase_variance = float(np.var(phase))
    if prev_amplitude is not None and len(prev_amplitude) == len(amplitude):
        temporal_delta = float(np.mean(np.abs(amplitude - prev_amplitude)))
    else:
        temporal_delta = 0.0
    return {
        "energy": energy,
        "amplitude_variance": variance,
        "phase_variance": phase_variance,
        "temporal_delta": temporal_delta,
    }
