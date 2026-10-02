"""
Hardware Abstraction Layer for CSI acquisition (section 11).

    AcquisitionInterface
    ├── SimulatedSensorAdapter   (implemented -- mandatory, section 42)
    ├── FileReplayAdapter        (implemented -- section 30)
    ├── ESP32Adapter             (live serial/UDP -- see docs/esp32.md)
    └── LinuxCSIAdapter          (live UDP/TCP/pipe -- Nexmon/PicoScenes/RPi -- see docs/csi.md)

Every frame produced by an adapter is tagged with a `DataProvenance` so the
rest of the pipeline (and the UI) always knows whether it is looking at real
sensor data or synthetic data (section 55 -- never blur this line).
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum


class DataProvenance(str, Enum):
    REAL_SENSOR_DATA = "real_sensor_data"
    SIMULATED_DATA = "simulated_data"
    REPLAYED_DATA = "replayed_data"


@dataclass
class CSIFrame:
    """A single CSI observation from one sensor link."""

    sensor_id: str
    link_id: str
    timestamp: float
    sequence: int
    subcarrier_amplitude: list[float]
    subcarrier_phase: list[float]
    rssi_dbm: float
    provenance: DataProvenance
    channel: int = 6
    bandwidth_mhz: int = 20
    antenna: int = 0
    # Only ever populated by the simulator, and only used for evaluation /
    # development -- never shown to the spatial ML engine as if it were an
    # observation. See GROUND_TRUTH handling in ml/baseline.py.
    debug_ground_truth: dict | None = None


@dataclass
class SensorHealth:
    sensor_id: str
    status: str  # online | offline | degraded
    packet_loss_pct: float = 0.0
    latency_ms: float = 0.0
    last_seen: float = field(default_factory=time.time)


class AcquisitionInterface(abc.ABC):
    """All CSI sources implement this so the pipeline is hardware-independent."""

    name: str = "abstract"
    provenance: DataProvenance = DataProvenance.REAL_SENSOR_DATA

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin producing frames."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop producing frames and release resources."""

    @abc.abstractmethod
    async def read_frame(self) -> CSIFrame | None:
        """Return the next available frame, or None if none is ready yet."""

    @abc.abstractmethod
    def health(self) -> list[SensorHealth]:
        """Current connectivity/quality info for all sensors this adapter manages."""


class UnsupportedHardwareError(RuntimeError):
    """Raised by hardware adapters that are not yet implemented on this platform."""
