"""
MappingEngine -- the runtime core.

    CSIFrame -> SignalProcessingPipeline -> BaselineHeuristicModel
             -> VoxelGrid.deposit()  (per-link local activity, section 24)
             -> aggregate_estimate() -> VoxelGrid.deposit() (room-level blob)
             -> cluster_voxels() -> Tracker.update() (sections 16, 33)
             -> snapshot() consumed by REST/WebSocket layer

Every produced value carries a provenance label (section 55) and this engine
never fabricates a detection: with zero active sensors it reports zero
occupancy and LOW confidence rather than guessing.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from app.acquisition.base import CSIFrame, DataProvenance
from app.ml.interfaces import EstimateSource
from app.ml.registry import get_active_model
from app.mapping.voxel_grid import VoxelGrid
from app.signal.pipeline import SignalProcessingPipeline
from app.tracking.tracker import Tracker, TrackedObject


@dataclass
class SensorRuntimeInfo:
    sensor_id: str
    x: float
    y: float
    z: float
    status: str = "offline"
    last_seen: float = 0.0
    packet_loss_pct: float = 0.0
    latency_ms: float = 0.0
    csi_hz: float = 0.0
    _frame_times: list[float] = field(default_factory=list)

    def note_frame(self) -> None:
        now = time.time()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t < 2.0]
        self.csi_hz = len(self._frame_times) / 2.0
        self.last_seen = now
        self.status = "online"


class MappingEngine:
    def __init__(self, bounds_m: tuple[float, float, float] = (5.0, 5.0, 3.0), resolution_m: float = 0.20):
        self.grid = VoxelGrid(bounds_m, resolution_m)
        self.pipeline = SignalProcessingPipeline()
        self.model = get_active_model()
        self.tracker = Tracker()
        self.sensors: dict[str, SensorRuntimeInfo] = {}
        self.latest_features: dict[str, dict] = {}
        self.link_to_sensor: dict[str, str] = {}
        self.last_tick: float = time.time()
        self.frame_count: int = 0
        self.rejected_count: int = 0
        self.data_provenance: DataProvenance = DataProvenance.SIMULATED_DATA
        self.baseline_snapshot: dict | None = None  # set by calibration (section 23)
        self._change_state: str = "UNCHANGED"
        self.last_snapshot: dict = {}

    def set_sensor_positions(self, positions: dict[str, tuple[float, float, float]]) -> None:
        for sensor_id, (x, y, z) in positions.items():
            existing = self.sensors.get(sensor_id)
            if existing:
                existing.x, existing.y, existing.z = x, y, z
            else:
                self.sensors[sensor_id] = SensorRuntimeInfo(sensor_id=sensor_id, x=x, y=y, z=z)

    def reset_runtime_state(self) -> None:
        """Clear map/tracker/feature state when switching acquisition modes."""
        self.grid.voxels.clear()
        self.tracker.reset()
        self.latest_features.clear()
        self.link_to_sensor.clear()
        self.frame_count = 0
        self.rejected_count = 0
        self.last_snapshot = {}
        # Keep calibrated baseline; drop live sensor runtime until new frames arrive
        self.sensors.clear()

    def ingest(self, frame: CSIFrame) -> dict | None:
        self.data_provenance = frame.provenance
        self.link_to_sensor[frame.link_id] = frame.sensor_id

        sensor = self.sensors.get(frame.sensor_id)
        if sensor is None:
            sensor = SensorRuntimeInfo(sensor_id=frame.sensor_id, x=0.0, y=0.0, z=2.0)
            self.sensors[frame.sensor_id] = sensor
        sensor.note_frame()

        processed = self.pipeline.process(frame)
        self.frame_count += 1
        if not processed.valid:
            self.rejected_count += 1
            return {
                "sensor_id": frame.sensor_id,
                "link_id": frame.link_id,
                "timestamp": frame.timestamp,
                "valid": False,
                "reject_reason": processed.reject_reason,
            }

        self.latest_features[frame.link_id] = processed.features

        # Local, single-link activity -> small localized bump near that sensor.
        # This reflects "this link's channel is disturbed", not a resolved
        # object position -- it is intentionally a soft, decaying splat.
        link_scores = self.model.score_links({frame.link_id: processed.features})
        score = link_scores.get(frame.link_id, 0.0)
        if score > 0.05:
            # RF-intensity/heatmap contribution only -- deliberately NOT fed
            # into occupancy_probability, since a single link's activity
            # doesn't resolve to "there is an object at the sensor" and would
            # otherwise spawn spurious clusters glued to every sensor.
            self.grid.deposit(
                center=(sensor.x, sensor.y, 1.0),
                occupancy=0.0,
                movement=0.0,
                rf_intensity=score,
                confidence=0.35,
                radius_m=1.0,
            )

        return {
            "sensor_id": frame.sensor_id,
            "link_id": frame.link_id,
            "timestamp": frame.timestamp,
            "valid": True,
            "provenance": frame.provenance.value,
            "amplitude": [round(v, 4) for v in processed.amplitude.tolist()],
            "phase": [round(v, 4) for v in processed.phase.tolist()],
            "raw_amplitude": [round(v, 4) for v in processed.raw_amplitude],
            "features": processed.features,
            "activity_score": round(score, 3) if score else 0.0,
        }

    def tick(self) -> dict:
        """Run once per UI/websocket broadcast interval: compute the
        room-level estimate, update the voxel grid, cluster it into
        candidate objects, update tracks, decay the grid, return a
        snapshot."""
        now = time.time()
        dt = max(1e-3, now - self.last_tick)
        self.last_tick = now

        # Mark offline sensors first, then drop features from offline links so
        # they cannot inflate occupancy after a sensor disconnects.
        self._mark_stale_sensors()
        online_ids = {sid for sid, s in self.sensors.items() if s.status == "online"}
        stale_links = [
            lid
            for lid, sid in self.link_to_sensor.items()
            if sid not in online_ids
        ]
        for lid in stale_links:
            self.latest_features.pop(lid, None)

        sensor_positions = {sid: (s.x, s.y, s.z) for sid, s in self.sensors.items()}
        self.model.configure_topology(sensor_positions, self.link_to_sensor)
        estimate = self.model.predict(self.latest_features)

        if estimate.position is not None:
            self.grid.deposit(
                center=estimate.position,
                occupancy=estimate.occupancy_probability,
                movement=estimate.movement_probability,
                rf_intensity=estimate.occupancy_probability * 0.5,
                confidence=estimate.confidence,
                radius_m=0.8,
            )

        clusters = self._cluster_voxels(threshold=0.28)
        tracked = self.tracker.update(clusters, dt)

        self.grid.decay(factor=0.8)

        self.last_snapshot = self.snapshot(estimate=estimate, tracked=tracked)
        return self.last_snapshot

    def _cluster_voxels(self, threshold: float = 0.28) -> list[dict]:
        """Union-adjacent-voxels-above-threshold into candidate object
        blobs (a simple connected-components pass), then return each
        cluster's occupancy-weighted centroid. This is how "how many
        objects / where" is derived -- not a trained detector."""
        active = {k: v for k, v in self.grid.voxels.items() if v.occupancy_probability >= threshold}
        visited: set[tuple[int, int, int]] = set()
        clusters: list[dict] = []

        for start in active:
            if start in visited:
                continue
            stack = [start]
            visited.add(start)
            members = []
            while stack:
                cur = stack.pop()
                members.append(cur)
                ci, cj, ck = cur
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        for dk in (-1, 0, 1):
                            if di == dj == dk == 0:
                                continue
                            nb = (ci + di, cj + dj, ck + dk)
                            if nb in active and nb not in visited:
                                visited.add(nb)
                                stack.append(nb)

            total_w = sum(active[m].occupancy_probability for m in members)
            if total_w <= 0:
                continue
            wx = sum(self.grid.index_to_world(*m)[0] * active[m].occupancy_probability for m in members) / total_w
            wy = sum(self.grid.index_to_world(*m)[1] * active[m].occupancy_probability for m in members) / total_w
            wz = sum(self.grid.index_to_world(*m)[2] * active[m].occupancy_probability for m in members) / total_w
            conf = max(active[m].confidence for m in members)
            clusters.append({"x": wx, "y": wy, "z": wz, "confidence": conf, "voxel_count": len(members)})

        return clusters

    def _mark_stale_sensors(self, timeout_s: float = 3.0) -> None:
        now = time.time()
        for sensor in self.sensors.values():
            if sensor.last_seen and now - sensor.last_seen > timeout_s:
                sensor.status = "offline"
                sensor.csi_hz = 0.0

    def sync_adapter_health(self, health_list) -> None:
        """Copy packet_loss / status from acquisition adapter health into runtime sensors."""
        for h in health_list or []:
            sid = getattr(h, "sensor_id", None)
            if not sid:
                continue
            sensor = self.sensors.get(sid)
            if sensor is None:
                continue
            sensor.packet_loss_pct = float(getattr(h, "packet_loss_pct", 0.0) or 0.0)
            sensor.latency_ms = float(getattr(h, "latency_ms", 0.0) or 0.0)
            # Do not force offline here — frame timeouts own that path


    def apply_calibration_baseline(self, baseline: dict) -> None:
        self.baseline_snapshot = baseline

    def compute_change_state(self, current_occupancy: float) -> str:
        if self.baseline_snapshot is None:
            return "NO_BASELINE"
        baseline_occ = self.baseline_snapshot.get("occupancy_probability", 0.0)
        delta = current_occupancy - baseline_occ
        if delta > 0.25:
            state = "NEW_ACTIVITY"
        elif delta < -0.25:
            state = "REMOVED_ACTIVITY"
        elif abs(delta) < 0.05:
            state = "UNCHANGED"
        else:
            state = "CHANGED"
        self._change_state = state
        return state

    def snapshot(self, estimate=None, tracked: list[TrackedObject] | None = None) -> dict:
        online_sensors = [s for s in self.sensors.values() if s.status == "online"]
        avg_hz = round(sum(s.csi_hz for s in online_sensors) / len(online_sensors), 1) if online_sensors else 0.0

        occupancy_probability = estimate.occupancy_probability if estimate else 0.0
        movement_probability = estimate.movement_probability if estimate else 0.0
        confidence = estimate.confidence if estimate else 0.0
        change_state = self.compute_change_state(occupancy_probability)

        return {
            "timestamp": time.time(),
            "provenance": self.data_provenance.value,
            "sensors": [
                {
                    "id": s.sensor_id,
                    "status": s.status,
                    "position": [s.x, s.y, s.z],
                    "csi_hz": s.csi_hz,
                    "packet_loss_pct": s.packet_loss_pct,
                    "latency_ms": s.latency_ms,
                }
                for s in self.sensors.values()
            ],
            "environment": {
                "bounds_m": list(self.grid.bounds_m),
                "voxel_resolution_m": self.grid.resolution_m,
                "occupancy_count_estimate": len(tracked) if tracked is not None else 0,
                "occupancy_probability": occupancy_probability,
                "movement_probability": movement_probability,
                "confidence": confidence,
                "avg_csi_hz": avg_hz,
                "change_state": change_state,
                "model": getattr(self.model, "name", "unknown"),
                "model_is_baseline": (
                    bool(getattr(self.model, "validated", False) is False)
                    and "baseline" in str(getattr(self.model, "name", "")).lower()
                ),
                "model_validated": bool(getattr(self.model, "validated", False)),
            },
            "objects": [
                {
                    "id": o.id,
                    "x": round(o.x, 2),
                    "y": round(o.y, 2),
                    "z": round(o.z, 2),
                    "velocity_mps": round(o.speed_mps, 2),
                    "confidence": round(o.confidence, 2),
                    "trail": [[round(p[0], 2), round(p[1], 2)] for p in o.trail[-20:]],
                    "source": EstimateSource.MODEL_PREDICTION.value,
                }
                for o in (tracked or [])
            ],
            "voxels": self.grid.as_sparse_list(),
            "frame_count": self.frame_count,
            "rejected_count": self.rejected_count,
        }
