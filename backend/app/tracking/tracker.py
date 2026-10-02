"""
Constant-velocity multi-object tracker with nearest-neighbor association.

Improvements over the pure nearest-neighbor baseline:
  - Predicts each track forward by dt before matching (reduces ID swaps)
  - Exponentially smoothed velocity
  - Confidence decays on missed ticks
  - Tracks remain anonymous (no identity recognition claim)
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class TrackedObject:
    id: str
    x: float
    y: float
    z: float
    vx: float = 0.0
    vy: float = 0.0
    confidence: float = 0.0
    missed_ticks: int = 0
    last_seen: float = field(default_factory=time.time)
    trail: list[tuple[float, float, float]] = field(default_factory=list)
    hits: int = 1

    @property
    def speed_mps(self) -> float:
        return math.hypot(self.vx, self.vy)

    def predicted(self, dt: float) -> tuple[float, float]:
        return (self.x + self.vx * dt, self.y + self.vy * dt)


class Tracker:
    def __init__(
        self,
        max_match_distance_m: float = 1.2,
        max_missed_ticks: int = 8,
        trail_length: int = 40,
        velocity_smoothing: float = 0.35,
    ):
        self.max_match_distance_m = max_match_distance_m
        self.max_missed_ticks = max_missed_ticks
        self.trail_length = trail_length
        self.velocity_smoothing = velocity_smoothing
        self.objects: dict[str, TrackedObject] = {}

    def update(self, detections: list[dict], dt: float) -> list[TrackedObject]:
        """detections: [{"x":..,"y":..,"z":..,"confidence":..}, ...]"""
        dt = max(dt, 1e-3)
        unmatched = list(detections)

        # Greedy match: for each existing track, find nearest unmatched detection
        # using predicted position.
        for obj in list(self.objects.values()):
            px, py = obj.predicted(dt)
            best_idx, best_dist = None, self.max_match_distance_m
            for idx, det in enumerate(unmatched):
                dist = math.hypot(px - det["x"], py - det["y"])
                if dist < best_dist:
                    best_idx, best_dist = idx, dist

            if best_idx is not None:
                det = unmatched.pop(best_idx)
                dx, dy = det["x"] - obj.x, det["y"] - obj.y
                alpha = self.velocity_smoothing
                measured_vx, measured_vy = dx / dt, dy / dt
                obj.vx = (1 - alpha) * obj.vx + alpha * measured_vx
                obj.vy = (1 - alpha) * obj.vy + alpha * measured_vy
                obj.x = det["x"]
                obj.y = det["y"]
                obj.z = det.get("z", obj.z)
                obj.confidence = min(1.0, det.get("confidence", obj.confidence) * 0.7 + obj.confidence * 0.3)
                obj.missed_ticks = 0
                obj.hits += 1
                obj.last_seen = time.time()
                obj.trail.append((obj.x, obj.y, obj.last_seen))
                if len(obj.trail) > self.trail_length:
                    obj.trail.pop(0)
            else:
                # Coast on constant-velocity model
                obj.x, obj.y = obj.predicted(dt)
                obj.missed_ticks += 1
                obj.vx *= 0.85
                obj.vy *= 0.85
                obj.confidence *= 0.85

        for det in unmatched:
            new_id = f"obj-{uuid.uuid4().hex[:6]}"
            self.objects[new_id] = TrackedObject(
                id=new_id,
                x=det["x"],
                y=det["y"],
                z=det.get("z", 1.0),
                confidence=det.get("confidence", 0.0),
                trail=[(det["x"], det["y"], time.time())],
            )

        dead = [oid for oid, o in self.objects.items() if o.missed_ticks > self.max_missed_ticks]
        for oid in dead:
            del self.objects[oid]

        return list(self.objects.values())

    def reset(self) -> None:
        self.objects.clear()
