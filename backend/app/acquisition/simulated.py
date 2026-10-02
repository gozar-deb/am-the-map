"""
SimulatedSensorAdapter -- section 42 (mandatory).

Generates synthetic CSI-like signals: subcarrier amplitude/phase driven by a
small set of simulated moving "objects" plus noise, so that the rest of the
pipeline (signal processing -> baseline ML -> voxel mapping) has something
non-trivial to act on. Also injects packet loss and occasional environmental
"events" (e.g. a new object appearing) so change-detection has something to
find.

Every frame is tagged SIMULATED_DATA. The synthetic object positions are
attached as `debug_ground_truth` purely so the evaluation dashboard can score
the baseline model against a known answer -- they are never fed to the ML
engine as an observation.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass, field

from app.acquisition.base import (
    AcquisitionInterface,
    CSIFrame,
    DataProvenance,
    SensorHealth,
)


@dataclass
class SimObject:
    id: str
    x: float
    y: float
    z: float
    vx: float
    vy: float
    moving: bool = True


@dataclass
class SimSensor:
    sensor_id: str
    x: float
    y: float
    z: float
    sampling_hz: float = 20.0


@dataclass
class SimulationConfig:
    room_x: float = 5.0
    room_y: float = 5.0
    room_z: float = 3.0
    n_subcarriers: int = 56
    noise_floor: float = 0.05
    packet_loss_base_pct: float = 0.5
    object_count: int = 2


class SimulatedSensorAdapter(AcquisitionInterface):
    name = "simulated"
    provenance = DataProvenance.SIMULATED_DATA

    def __init__(self, sensors: list[SimSensor] | None = None, config: SimulationConfig | None = None):
        self.config = config or SimulationConfig()
        self.sensors = sensors or self._default_sensors()
        self._objects: list[SimObject] = self._spawn_objects()
        self._running = False
        self._seq = 0
        self._last_tick = time.time()
        self._queue: asyncio.Queue[CSIFrame] = asyncio.Queue(maxsize=2000)
        self._task: asyncio.Task | None = None

    def _default_sensors(self) -> list[SimSensor]:
        return [
            SimSensor("NODE-01", 0.0, 0.0, 2.2),
            SimSensor("NODE-02", self.config.room_x, 0.0, 2.2),
            SimSensor("NODE-03", self.config.room_x / 2, self.config.room_y, 2.2),
        ]

    def _spawn_objects(self) -> list[SimObject]:
        objs = []
        for i in range(self.config.object_count):
            objs.append(
                SimObject(
                    id=f"sim-obj-{i}",
                    x=random.uniform(0.5, self.config.room_x - 0.5),
                    y=random.uniform(0.5, self.config.room_y - 0.5),
                    z=1.0,
                    vx=random.uniform(-0.4, 0.4),
                    vy=random.uniform(-0.4, 0.4),
                    moving=random.random() > 0.3,
                )
            )
        return objs

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        period = 1.0 / max(1.0, min(s.sampling_hz for s in self.sensors))
        try:
            while self._running:
                self._step_world(period)
                for sensor in self.sensors:
                    frame = self._synthesize_frame(sensor)
                    if frame is not None:
                        if self._queue.full():
                            _ = self._queue.get_nowait()
                        self._queue.put_nowait(frame)
                await asyncio.sleep(period)
        except asyncio.CancelledError:
            return

    def _step_world(self, dt: float) -> None:
        for obj in self._objects:
            if not obj.moving:
                continue
            obj.x += obj.vx * dt
            obj.y += obj.vy * dt
            if obj.x < 0.2 or obj.x > self.config.room_x - 0.2:
                obj.vx *= -1
            if obj.y < 0.2 or obj.y > self.config.room_y - 0.2:
                obj.vy *= -1
            # occasionally change behaviour so movement probability isn't constant
            if random.random() < 0.002:
                obj.moving = not obj.moving
            if random.random() < 0.0005:
                obj.vx = random.uniform(-0.4, 0.4)
                obj.vy = random.uniform(-0.4, 0.4)

    def _synthesize_frame(self, sensor: SimSensor) -> CSIFrame | None:
        # simulate packet loss
        if random.uniform(0, 100) < self.config.packet_loss_base_pct:
            return None

        n = self.config.n_subcarriers
        amplitude = [1.0 + random.gauss(0, self.config.noise_floor) for _ in range(n)]
        phase = [random.uniform(-math.pi, math.pi) * 0.02 for _ in range(n)]

        # Each nearby/moving object perturbs amplitude & phase, roughly like
        # multipath fading from a body in the Fresnel zone of the link. This
        # is a plausible *toy* signal model for development, not a validated
        # RF propagation simulation.
        for obj in self._objects:
            dist = math.dist((sensor.x, sensor.y, sensor.z), (obj.x, obj.y, obj.z))
            proximity = max(0.0, 1.0 - dist / 6.0)
            speed = math.hypot(obj.vx, obj.vy) if obj.moving else 0.0
            for k in range(n):
                fade = proximity * (0.15 + 0.1 * math.sin(k * 0.3 + dist))
                amplitude[k] += fade
                phase[k] += proximity * speed * math.sin(k * 0.5 + time.time() * 2)

        self._seq += 1
        ground_truth = {
            "objects": [
                {"id": o.id, "x": round(o.x, 3), "y": round(o.y, 3), "z": round(o.z, 3), "moving": o.moving}
                for o in self._objects
            ]
        }
        return CSIFrame(
            sensor_id=sensor.sensor_id,
            link_id=f"{sensor.sensor_id}<->AP",
            timestamp=time.time(),
            sequence=self._seq,
            subcarrier_amplitude=amplitude,
            subcarrier_phase=phase,
            rssi_dbm=-40 - random.uniform(0, 15),
            provenance=DataProvenance.SIMULATED_DATA,
            debug_ground_truth=ground_truth,
        )

    async def read_frame(self) -> CSIFrame | None:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def health(self) -> list[SensorHealth]:
        return [
            SensorHealth(
                sensor_id=s.sensor_id,
                status="online" if self._running else "offline",
                packet_loss_pct=self.config.packet_loss_base_pct,
                latency_ms=random.uniform(2, 8),
            )
            for s in self.sensors
        ]
