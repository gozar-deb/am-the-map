"""SensorManager -- coordinates whichever AcquisitionInterface is active and
exposes a single, hardware-independent stream of CSIFrame objects."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from app.acquisition.base import AcquisitionInterface, CSIFrame, SensorHealth
from app.acquisition.esp32 import ESP32Adapter
from app.acquisition.file_replay import FileReplayAdapter
from app.acquisition.linux_csi import LinuxCSIAdapter
from app.acquisition.simulated import SimulatedSensorAdapter
from app.core.logging import get_logger

logger = get_logger("acquisition.manager")

ADAPTER_REGISTRY = {
    "simulated": SimulatedSensorAdapter,
    "esp32": ESP32Adapter,
    "linux_csi": LinuxCSIAdapter,
    "file_replay": FileReplayAdapter,
}


class SensorManager:
    def __init__(self) -> None:
        self.adapter: Optional[AcquisitionInterface] = None
        self.mode: str = "stopped"
        self._running = False

    async def start(self, mode: str, **kwargs) -> None:
        if self.adapter is not None:
            await self.stop()
        if mode not in ADAPTER_REGISTRY:
            raise ValueError(f"Unknown acquisition mode '{mode}'. Options: {list(ADAPTER_REGISTRY)}")
        self.adapter = ADAPTER_REGISTRY[mode](**kwargs)
        self.mode = mode
        await self.adapter.start()
        self._running = True
        logger.info("acquisition.started", mode=mode)

    async def stop(self) -> None:
        if self.adapter is not None:
            await self.adapter.stop()
        self._running = False
        self.mode = "stopped"
        logger.info("acquisition.stopped")

    @property
    def running(self) -> bool:
        return self._running

    def health(self) -> list[SensorHealth]:
        if not self.adapter:
            return []
        return self.adapter.health()

    async def frames(self, poll_interval: float = 0.01) -> AsyncIterator[CSIFrame]:
        """Yield frames as they arrive, without busy-looping too hard.

        If the adapter exposes ``finished`` (file replay), stop when the
        recording is exhausted instead of spinning forever on None.
        """
        idle_rounds = 0
        while self._running and self.adapter is not None:
            frame = await self.adapter.read_frame()
            if frame is None:
                if getattr(self.adapter, "finished", False):
                    logger.info("acquisition.adapter_finished", mode=self.mode)
                    break
                idle_rounds += 1
                # Back off slightly under sustained idle to reduce CPU
                await asyncio.sleep(min(poll_interval * (1 + idle_rounds * 0.05), 0.2))
                continue
            idle_rounds = 0
            yield frame


sensor_manager = SensorManager()
