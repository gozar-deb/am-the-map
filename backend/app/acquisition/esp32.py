"""
ESP32Adapter -- live CSI acquisition from ESP32 / ESP32-S3 boards.

Supports the two most common transports used by CSI firmware forks
(ESP32-CSI-Tool and derivatives):

  1. USB serial (one board on a desk)
  2. UDP (multiple boards on the LAN)

Packet formats accepted (auto-detected per line/datagram):

  • JSON lines:
      {"sensor_id":"NODE-01","amplitude":[...],"phase":[...],"rssi":-48,"seq":12}
  • ESP32-CSI-Tool CSV rows that contain a CSI_DATA field
  • Plain space/comma-separated amplitude then phase vectors

Provenance is always REAL_SENSOR_DATA. If the serial port / UDP socket
cannot be opened, start() raises a clear error — it never fabricates frames.

Requires:  pip install pyserial   (optional; only needed for serial transport)
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import socket
import time
from typing import Optional

from app.acquisition.base import (
    AcquisitionInterface,
    CSIFrame,
    DataProvenance,
    SensorHealth,
)
from app.core.logging import get_logger

logger = get_logger("acquisition.esp32")

# pyserial is optional so the rest of the platform still installs cleanly.
try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def _parse_float_list(raw: str) -> list[float]:
    """Extract a list of floats from a CSV/JSON-ish substring."""
    raw = raw.strip().strip("[]()\"'")
    if not raw:
        return []
    parts = re.split(r"[\s,;]+", raw)
    out: list[float] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            out.append(float(p))
        except ValueError:
            continue
    return out


def _complex_to_amp_phase(values: list[float]) -> tuple[list[float], list[float]]:
    """Interpret flat [re, im, re, im, ...] as amplitude/phase."""
    amp: list[float] = []
    phase: list[float] = []
    for i in range(0, len(values) - 1, 2):
        re_v, im_v = values[i], values[i + 1]
        amp.append(math.hypot(re_v, im_v))
        phase.append(math.atan2(im_v, re_v))
    return amp, phase


def parse_csi_payload(
    text: str,
    default_sensor_id: str = "ESP32-01",
    sequence: int = 0,
) -> Optional[CSIFrame]:
    """
    Best-effort parser for common ESP32 CSI line formats.
    Returns None if the line is not recognisable CSI data.
    """
    text = text.strip()
    if not text or text.startswith("#"):
        return None

    # --- JSON ---
    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        amp = obj.get("amplitude") or obj.get("subcarrier_amplitude") or obj.get("amp")
        phase = obj.get("phase") or obj.get("subcarrier_phase")
        if amp is None and "csi" in obj:
            csi = obj["csi"]
            if isinstance(csi, list) and csi and isinstance(csi[0], (int, float)):
                amp, phase = _complex_to_amp_phase([float(x) for x in csi])
            elif isinstance(csi, list) and csi and isinstance(csi[0], (list, tuple)):
                amp = [math.hypot(float(c[0]), float(c[1])) for c in csi]
                phase = [math.atan2(float(c[1]), float(c[0])) for c in csi]
        if amp is None:
            return None
        amp = [float(x) for x in amp]
        if phase is None:
            phase = [0.0] * len(amp)
        else:
            phase = [float(x) for x in phase]
        sensor_id = str(obj.get("sensor_id") or obj.get("mac") or obj.get("node") or default_sensor_id)
        link_id = str(obj.get("link_id") or f"{sensor_id}<->AP")
        return CSIFrame(
            sensor_id=sensor_id,
            link_id=link_id,
            timestamp=float(obj.get("timestamp") or time.time()),
            sequence=int(obj.get("seq") or obj.get("sequence") or sequence),
            subcarrier_amplitude=amp,
            subcarrier_phase=phase,
            rssi_dbm=float(obj.get("rssi") or obj.get("rssi_dbm") or -60.0),
            provenance=DataProvenance.REAL_SENSOR_DATA,
            channel=int(obj.get("channel") or 6),
            bandwidth_mhz=int(obj.get("bandwidth_mhz") or obj.get("bandwidth") or 20),
            antenna=int(obj.get("antenna") or obj.get("ant") or 0),
        )

    # --- ESP32-CSI-Tool style CSV ---
    lower = text.lower()
    if "csi_data" in lower or "csi," in lower or text.count(",") > 20:
        parts = text.split(",")
        csi_blob = None
        for i, p in enumerate(parts):
            if "csi" in p.lower() and i + 1 < len(parts):
                csi_blob = ",".join(parts[i + 1 :])
                break
        if csi_blob is None:
            candidates = sorted(
                parts,
                key=lambda x: sum(c.isdigit() or c in ".- " for c in x),
                reverse=True,
            )
            csi_blob = candidates[0] if candidates else ""
        values = _parse_float_list(csi_blob)
        if len(values) < 4:
            return None
        if len(values) >= 8 and len(values) % 2 == 0:
            amp, phase = _complex_to_amp_phase(values)
        else:
            amp = values
            phase = [0.0] * len(amp)
        rssi = -60.0
        channel = 6
        for p in parts[:20]:
            p = p.strip()
            try:
                v = float(p)
                if -100 <= v <= -10:
                    rssi = v
                elif 1 <= v <= 14 and v == int(v):
                    channel = int(v)
            except ValueError:
                continue
        sensor_id = default_sensor_id
        for p in parts[:8]:
            if re.match(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$", p.strip()):
                sensor_id = p.strip().replace(":", "")[-6:]
                break
        return CSIFrame(
            sensor_id=sensor_id,
            link_id=f"{sensor_id}<->AP",
            timestamp=time.time(),
            sequence=sequence,
            subcarrier_amplitude=amp,
            subcarrier_phase=phase,
            rssi_dbm=rssi,
            provenance=DataProvenance.REAL_SENSOR_DATA,
            channel=channel,
        )

    # --- Plain numeric line ---
    if "|" in text:
        left, right = text.split("|", 1)
        amp = _parse_float_list(left)
        phase = _parse_float_list(right)
        if amp:
            if not phase:
                phase = [0.0] * len(amp)
            return CSIFrame(
                sensor_id=default_sensor_id,
                link_id=f"{default_sensor_id}<->AP",
                timestamp=time.time(),
                sequence=sequence,
                subcarrier_amplitude=amp,
                subcarrier_phase=phase,
                rssi_dbm=-60.0,
                provenance=DataProvenance.REAL_SENSOR_DATA,
            )
    values = _parse_float_list(text)
    if len(values) >= 8:
        if len(values) % 2 == 0:
            amp, phase = _complex_to_amp_phase(values)
        else:
            amp, phase = values, [0.0] * len(values)
        return CSIFrame(
            sensor_id=default_sensor_id,
            link_id=f"{default_sensor_id}<->AP",
            timestamp=time.time(),
            sequence=sequence,
            subcarrier_amplitude=amp,
            subcarrier_phase=phase,
            rssi_dbm=-60.0,
            provenance=DataProvenance.REAL_SENSOR_DATA,
        )
    return None


class ESP32Adapter(AcquisitionInterface):
    name = "esp32"
    provenance = DataProvenance.REAL_SENSOR_DATA

    def __init__(
        self,
        port: str | None = None,
        baud: int = 921600,
        udp_host: str | None = None,
        udp_port: int | None = None,
        sensor_id: str = "ESP32-01",
        **_kwargs,
    ):
        """
        port:      serial device (e.g. /dev/ttyUSB0, COM3). Auto-detect if None
                   and udp is not set.
        baud:      serial baud rate (ESP32-CSI-Tool commonly uses 921600 or 115200)
        udp_host:  bind address for UDP listener (default 0.0.0.0)
        udp_port:  UDP port the firmware sends CSI to (e.g. 5005)
        sensor_id: fallback sensor id when the packet does not carry one
        """
        self.port = port
        self.baud = baud
        self.udp_host = udp_host or "0.0.0.0"
        self.udp_port = udp_port
        self.default_sensor_id = sensor_id
        self._running = False
        self._queue: asyncio.Queue[CSIFrame] = asyncio.Queue(maxsize=2000)
        self._task: asyncio.Task | None = None
        self._seq = 0
        self._serial = None
        self._sock: socket.socket | None = None
        self._frames_received = 0
        self._last_frame_ts = 0.0
        self._sensor_ids: set[str] = set()
        self._seq_seen = 0
        self._seq_gaps = 0
        self._last_seq: int | None = None

    async def start(self) -> None:
        if self.udp_port is not None:
            await self._start_udp()
        else:
            await self._start_serial()
        self._running = True
        self._task = asyncio.create_task(self._reader_loop())
        logger.info(
            "esp32.started",
            transport="udp" if self.udp_port else "serial",
            port=self.port or self.udp_port,
        )

    async def _start_serial(self) -> None:
        if not HAS_SERIAL:
            raise RuntimeError(
                "pyserial is required for ESP32 serial acquisition. "
                "Install with:  pip install pyserial"
            )
        port = self.port
        if not port:
            ports = list(serial.tools.list_ports.comports())
            preferred = [
                p
                for p in ports
                if any(
                    k in (p.description or "").lower() or k in (p.device or "").lower()
                    for k in ("cp210", "ch340", "ftdi", "usb serial", "uart", "esp")
                )
            ]
            pick = preferred[0] if preferred else (ports[0] if ports else None)
            if pick is None:
                raise RuntimeError(
                    "No serial port found. Plug in an ESP32 over USB, or pass "
                    "port='/dev/ttyUSB0' (Linux) / 'COM3' (Windows), or use "
                    "udp_port=... for network firmware."
                )
            port = pick.device
            self.port = port
        try:
            self._serial = serial.Serial(port, self.baud, timeout=0.05)
        except Exception as e:
            raise RuntimeError(f"Could not open serial port {port}: {e}") from e

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

    async def _reader_loop(self) -> None:
        loop = asyncio.get_event_loop()
        buf = ""
        try:
            while self._running:
                line: Optional[str] = None
                if self._serial is not None:
                    try:
                        raw = await loop.run_in_executor(None, self._serial.readline)
                        if raw:
                            line = raw.decode("utf-8", errors="ignore")
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                elif self._sock is not None:
                    try:
                        data, _addr = await loop.sock_recvfrom(self._sock, 65535)
                        line = data.decode("utf-8", errors="ignore")
                    except (BlockingIOError, InterruptedError):
                        await asyncio.sleep(0.005)
                        continue
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                else:
                    await asyncio.sleep(0.1)
                    continue

                if not line:
                    await asyncio.sleep(0.001)
                    continue

                if self._serial is not None and not line.endswith("\n"):
                    buf += line
                    continue
                if self._serial is not None:
                    line = buf + line
                    buf = ""

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
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        logger.info("esp32.stopped", frames=self._frames_received)

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
