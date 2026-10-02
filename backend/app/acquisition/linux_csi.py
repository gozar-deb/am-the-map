"""
LinuxCSIAdapter -- live CSI from Linux CSI tools and Raspberry Pi.

Ordinary consumer WiFi adapters do NOT expose CSI. This adapter talks to
tools that *do*:

  • Nexmon CSI          (Raspberry Pi onboard WiFi, some Broadcom chips)
  • PicoScenes          (Intel / Atheros / etc.)
  • Atheros CSI Tool
  • Any process that emits the JSON / CSV / pipe formats documented below

Transports:

  1. UDP datagrams   (udp_host + udp_port)     -- common for Nexmon / PicoScenes
  2. Named pipe or file tail  (source_path)   -- log file or FIFO
  3. TCP stream      (tcp_host + tcp_port)    -- optional

Formats accepted (same parser family as ESP32Adapter):

  • JSON lines with amplitude/phase or complex CSI
  • CSV / space-separated numeric CSI matrices
  • amp | phase lines

Provenance is always REAL_SENSOR_DATA. start() fails clearly if the socket
or path cannot be opened — never fabricates frames.

Raspberry Pi tip:
  Install Nexmon CSI, point its UDP output at this adapter
  (e.g. mode=linux_csi, udp_port=5500).
"""
from __future__ import annotations

import asyncio
import socket
import time
from pathlib import Path
from typing import Optional

from app.acquisition.base import (
    AcquisitionInterface,
    CSIFrame,
    DataProvenance,
    SensorHealth,
)
from app.acquisition.esp32 import parse_csi_payload
from app.core.logging import get_logger

logger = get_logger("acquisition.linux_csi")


class LinuxCSIAdapter(AcquisitionInterface):
    name = "linux_csi"
    provenance = DataProvenance.REAL_SENSOR_DATA

    def __init__(
        self,
        interface: str | None = None,
        source_path: str | None = None,
        udp_host: str | None = None,
        udp_port: int | None = None,
        tcp_host: str | None = None,
        tcp_port: int | None = None,
        sensor_id: str = "CSI-NIC-01",
        **_kwargs,
    ):
        self.interface = interface
        self.source_path = source_path
        self.udp_host = udp_host or "0.0.0.0"
        self.udp_port = udp_port
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.default_sensor_id = sensor_id
        self._running = False
        self._queue: asyncio.Queue[CSIFrame] = asyncio.Queue(maxsize=2000)
        self._task: asyncio.Task | None = None
        self._seq = 0
        self._sock: socket.socket | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._file = None
        self._frames_received = 0
        self._last_frame_ts = 0.0
        self._sensor_ids: set[str] = set()
        self._seq_seen = 0
        self._seq_gaps = 0
        self._last_seq: int | None = None

    async def start(self) -> None:
        if self.udp_port is not None:
            await self._start_udp()
        elif self.tcp_host and self.tcp_port:
            await self._start_tcp()
        elif self.source_path:
            await self._start_file()
        else:
            raise RuntimeError(
                "LinuxCSIAdapter requires one of: "
                "udp_port=...,  tcp_host=+tcp_port=...,  or source_path=... "
                "(named pipe / log from Nexmon, PicoScenes, Atheros CSI Tool, etc.). "
                "Ordinary WiFi adapters do not expose CSI — see docs/csi.md."
            )
        self._running = True
        self._task = asyncio.create_task(self._reader_loop())
        logger.info(
            "linux_csi.started",
            transport=(
                "udp"
                if self.udp_port
                else "tcp"
                if self.tcp_host
                else "file"
            ),
            path=self.source_path,
            port=self.udp_port or self.tcp_port,
            interface=self.interface,
        )

    async def _start_udp(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.udp_host, int(self.udp_port)))
        except Exception as e:
            sock.close()
            raise RuntimeError(
                f"Could not bind UDP {self.udp_host}:{self.udp_port}: {e}"
            ) from e
        sock.setblocking(False)
        self._sock = sock

    async def _start_tcp(self) -> None:
        try:
            reader, writer = await asyncio.open_connection(
                self.tcp_host, int(self.tcp_port)
            )
        except Exception as e:
            raise RuntimeError(
                f"Could not connect TCP {self.tcp_host}:{self.tcp_port}: {e}"
            ) from e
        self._reader = reader
        self._writer = writer

    async def _start_file(self) -> None:
        path = Path(self.source_path)
        if str(path).endswith(".fifo") and not path.exists():
            import os
            os.mkfifo(path)
        if not path.exists():
            raise FileNotFoundError(
                f"CSI source path does not exist: {path}. "
                "Point source_path at a Nexmon/PicoScenes log or FIFO."
            )
        self._file = open(path, "r", encoding="utf-8", errors="ignore")
        try:
            self._file.seek(0, 2)
        except OSError:
            pass

    async def _reader_loop(self) -> None:
        loop = asyncio.get_event_loop()
        try:
            while self._running:
                line: Optional[str] = None
                if self._sock is not None:
                    try:
                        data, _addr = await loop.sock_recvfrom(self._sock, 65535)
                        line = data.decode("utf-8", errors="ignore")
                    except (BlockingIOError, InterruptedError):
                        await asyncio.sleep(0.005)
                        continue
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                elif self._reader is not None:
                    try:
                        raw = await self._reader.readline()
                        if not raw:
                            await asyncio.sleep(0.05)
                            continue
                        line = raw.decode("utf-8", errors="ignore")
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                elif self._file is not None:
                    try:
                        line = await loop.run_in_executor(None, self._file.readline)
                        if not line:
                            await asyncio.sleep(0.02)
                            continue
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                else:
                    await asyncio.sleep(0.1)
                    continue

                if not line:
                    continue

                for chunk in line.splitlines():
                    self._seq += 1
                    frame = parse_csi_payload(chunk, self.default_sensor_id, self._seq)
                    if frame is None:
                        continue
                    self._frames_received += 1
                    self._last_frame_ts = time.time()
                    self._sensor_ids.add(frame.sensor_id)
                    if self._last_seq is not None and frame.sequence > self._last_seq + 1:
                        self._seq_gaps += frame.sequence - self._last_seq - 1
                    self._last_seq = frame.sequence
                    self._seq_seen += 1
                    try:
                        self._queue.put_nowait(frame)
                    except asyncio.QueueFull:
                        try:
                            self._queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            self._queue.put_nowait(frame)
                        except asyncio.QueueFull:
                            pass
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
        logger.info("linux_csi.stopped", frames=self._frames_received)

    async def read_frame(self) -> CSIFrame | None:
        if not self._running:
            return None
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def health(self) -> list[SensorHealth]:
        now = time.time()
        online = (
            self._running and (now - self._last_frame_ts < 3.0)
            if self._last_frame_ts
            else self._running
        )
        total = self._seq_seen + self._seq_gaps
        loss = round(100.0 * self._seq_gaps / total, 1) if total > 0 else 0.0
        ids = self._sensor_ids or {self.default_sensor_id}
        return [
            SensorHealth(
                sensor_id=sid,
                status="online" if online else "offline",
                packet_loss_pct=loss,
                latency_ms=0.0,
                last_seen=self._last_frame_ts or now,
            )
            for sid in ids
        ]
