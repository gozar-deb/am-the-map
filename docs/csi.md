# Linux CSI Adapter (Nexmon, PicoScenes, Atheros, Raspberry Pi)

**Status: implemented** (`backend/app/acquisition/linux_csi.py`).

Ordinary consumer WiFi adapters **do not expose CSI**. This adapter connects
to tools that extract it:

- **Nexmon CSI** — Raspberry Pi onboard WiFi and some Broadcom chips
- **PicoScenes** — modern multi-chipset CSI platform
- **Atheros CSI Tool** — patched Atheros drivers

## Transports

| Transport | Parameters |
|-----------|------------|
| UDP listen | `udp_host` (default `0.0.0.0`), `udp_port` |
| TCP client | `tcp_host`, `tcp_port` |
| Named pipe / log tail | `source_path` (FIFO or growing log file) |

## Examples

```bash
# Raspberry Pi + Nexmon sending UDP CSI
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","udp_port":5500,"sensor_id":"RPI-01"}'

# Tail a PicoScenes / Atheros log
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","source_path":"/tmp/csi.log"}'

# TCP publisher
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","tcp_host":"127.0.0.1","tcp_port":9000}'
```

Packet formats are the same family as the ESP32 adapter (JSON lines,
CSV CSI matrices, `amp | phase` lines). See `docs/esp32.md`.

## What does **not** work

- Stock laptop / desktop WiFi drivers (Intel, Broadcom, MediaTek, Realtek
  consumer chips) — they do not export per-subcarrier CSI to userspace.
- Stock smartphone WiFi (iOS / Android) — no public CSI API; requires
  custom kernels / closed research firmwares that are not generally available.
- A normal USB WiFi dongle without a CSI-capable driver + tool chain.

If you only have a phone or a normal laptop, use the built-in simulator or
record real CSI elsewhere and replay it with `mode=file_replay`.
