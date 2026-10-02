"""
3D voxel environment representation (section 8).

Stored sparsely (dict keyed by integer voxel index) rather than as a dense
array, since most of a room is empty most of the time and dense arrays at
5cm resolution over a real room would be wasteful. Values decay each tick
(section 24 -- "use temporal smoothing to avoid unstable flickering")
instead of being overwritten, so detections fade gracefully rather than
popping in and out.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


VALID_RESOLUTIONS_M = (0.05, 0.10, 0.20, 0.50)


@dataclass
class VoxelState:
    occupancy_probability: float = 0.0
    movement_probability: float = 0.0
    rf_intensity: float = 0.0
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


class VoxelGrid:
    def __init__(
        self,
        bounds_m: tuple[float, float, float] = (5.0, 5.0, 3.0),
        resolution_m: float = 0.20,
    ):
        if resolution_m not in VALID_RESOLUTIONS_M:
            # Don't hard-fail on an unusual value -- just don't pretend it's
            # one of the documented presets (section 8: "do not assume high
            # resolution is always better").
            pass
        self.bounds_m = bounds_m
        self.resolution_m = resolution_m
        self.nx = max(1, math.ceil(bounds_m[0] / resolution_m))
        self.ny = max(1, math.ceil(bounds_m[1] / resolution_m))
        self.nz = max(1, math.ceil(bounds_m[2] / resolution_m))
        self.voxels: dict[tuple[int, int, int], VoxelState] = {}

    def world_to_index(self, x: float, y: float, z: float) -> tuple[int, int, int]:
        i = min(max(int(x / self.resolution_m), 0), self.nx - 1)
        j = min(max(int(y / self.resolution_m), 0), self.ny - 1)
        k = min(max(int(z / self.resolution_m), 0), self.nz - 1)
        return i, j, k

    def index_to_world(self, i: int, j: int, k: int) -> tuple[float, float, float]:
        return (
            (i + 0.5) * self.resolution_m,
            (j + 0.5) * self.resolution_m,
            (k + 0.5) * self.resolution_m,
        )

    def deposit(
        self,
        center: tuple[float, float, float],
        occupancy: float,
        movement: float,
        rf_intensity: float,
        confidence: float,
        radius_m: float = 0.6,
    ) -> None:
        """Splat a Gaussian-ish blob of probability around `center`, bounded
        to a small box for performance."""
        if occupancy <= 0.005 and movement <= 0.005 and rf_intensity <= 0.005:
            return
        # Guard zero/negative radius (would divide by zero in Gaussian falloff)
        radius_m = max(float(radius_m), 1e-6)
        cx, cy, cz = center
        ci, cj, ck = self.world_to_index(cx, cy, cz)
        span = max(1, int(math.ceil(radius_m / self.resolution_m)))
        now = time.time()
        sigma2 = max(2 * (radius_m / 2) ** 2, 1e-12)
        for di in range(-span, span + 1):
            for dj in range(-span, span + 1):
                for dk in range(-1, 2):
                    i, j, k = ci + di, cj + dj, ck + dk
                    if not (0 <= i < self.nx and 0 <= j < self.ny and 0 <= k < self.nz):
                        continue
                    # Always paint the center voxel; others use distance falloff
                    if (i, j, k) == (ci, cj, ck):
                        falloff = 1.0
                    else:
                        wx, wy, wz = self.index_to_world(i, j, k)
                        dist = math.dist((wx, wy, wz), (cx, cy, cz))
                        if dist > radius_m:
                            continue
                        falloff = math.exp(-(dist ** 2) / sigma2)
                    key = (i, j, k)
                    state = self.voxels.get(key) or VoxelState()
                    state.occupancy_probability = min(1.0, state.occupancy_probability + occupancy * falloff)
                    state.movement_probability = min(1.0, state.movement_probability + movement * falloff)
                    state.rf_intensity = min(1.0, state.rf_intensity + rf_intensity * falloff)
                    state.confidence = max(state.confidence, confidence * falloff)
                    state.timestamp = now
                    self.voxels[key] = state

    def decay(self, factor: float = 0.9, floor: float = 0.01) -> None:
        """Temporal smoothing: fade every voxel each tick instead of hard
        resets, and drop voxels that have decayed to near-nothing."""
        dead = []
        for key, state in self.voxels.items():
            state.occupancy_probability *= factor
            state.movement_probability *= factor
            state.rf_intensity *= factor
            if state.occupancy_probability < floor and state.rf_intensity < floor:
                dead.append(key)
        for key in dead:
            del self.voxels[key]

    def as_sparse_list(self, threshold: float = 0.04) -> list[dict]:
        out = []
        for (i, j, k), state in self.voxels.items():
            if state.occupancy_probability < threshold and state.rf_intensity < threshold:
                continue
            out.append(
                {
                    "x": i,
                    "y": j,
                    "z": k,
                    "world": self.index_to_world(i, j, k),
                    "occupancy_probability": round(state.occupancy_probability, 3),
                    "movement_probability": round(state.movement_probability, 3),
                    "rf_intensity": round(state.rf_intensity, 3),
                    "confidence": round(state.confidence, 3),
                    "timestamp": state.timestamp,
                }
            )
        return out

    def resize(self, bounds_m: tuple[float, float, float], resolution_m: float) -> None:
        self.__init__(bounds_m, resolution_m)  # type: ignore[misc]
