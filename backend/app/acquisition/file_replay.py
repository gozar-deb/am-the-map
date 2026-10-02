"""FileReplayAdapter -- replays a recorded session's CSI frames on their
original relative timing so replay reproduces the visualization/inference
timeline (section 30)."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from app.acquisition.base import AcquisitionInterface, CSIFrame, DataProvenance, SensorHealth


class FileReplayAdapter(AcquisitionInterface):
    name = "file_replay"
    provenance = DataProvenance.REPLAYED_DATA

    def __init__(self, recording_path: str | Path, speed: float = 1.0):
        self.recording_path = Path(recording_path)
        self.speed = speed
        self._frames: list[dict] = []
        self._idx = 0
        self._running = False
        self._start_wall = 0.0
        self._start_rec = 0.0

    async def start(self) -> None:
        if not self.recording_path.exists():
            raise FileNotFoundError(f"No recording at {self.recording_path}")
        with open(self.recording_path) as f:
            self._frames = [json.loads(line) for line in f if line.strip()]
        self._idx = 0
        self._running = True
        self._start_wall = time.time()
        self._start_rec = self._frames[0]["timestamp"] if self._frames else 0.0

    async def stop(self) -> None:
        self._running = False

    async def read_frame(self) -> CSIFrame | None:
        if not self._running or self._idx >= len(self._frames):
            return None
        raw = self._frames[self._idx]
        target_elapsed = (raw["timestamp"] - self._start_rec) / max(self.speed, 0.001)
        actual_elapsed = time.time() - self._start_wall
        if actual_elapsed < target_elapsed:
            await asyncio.sleep(min(target_elapsed - actual_elapsed, 0.5))
            return None
        self._idx += 1
        return CSIFrame(
            sensor_id=raw["sensor_id"],
            link_id=raw["link_id"],
            timestamp=raw["timestamp"],
            sequence=raw["sequence"],
            subcarrier_amplitude=raw["subcarrier_amplitude"],
            subcarrier_phase=raw["subcarrier_phase"],
            rssi_dbm=raw["rssi_dbm"],
            provenance=DataProvenance.REPLAYED_DATA,
            debug_ground_truth=raw.get("debug_ground_truth"),
        )

    def health(self) -> list[SensorHealth]:
        remaining = len(self._frames) - self._idx
        return [SensorHealth(sensor_id="replay", status="online" if remaining > 0 else "offline")]

    @property
    def finished(self) -> bool:
        return self._idx >= len(self._frames)
