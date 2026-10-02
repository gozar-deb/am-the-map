# Hardware

## Development Mode (no sensors required)

Any laptop, desktop, Raspberry Pi, NVIDIA Jetson, or Linux server. The
`SimulatedSensorAdapter` generates synthetic CSI-like signals so the full
pipeline works with zero physical hardware.

## Real Sensing Mode (live data)

**Ordinary consumer WiFi adapters, phones, and laptops do not expose CSI.**
You need specialized hardware + firmware:

| Source | Adapter | Status |
|--------|---------|--------|
| ESP32 / ESP32-S3 + CSI firmware | `mode=esp32` | **Live** — serial or UDP |
| Raspberry Pi + Nexmon CSI | `mode=linux_csi` | **Live** — UDP / pipe / TCP |
| PicoScenes / Atheros CSI Tool | `mode=linux_csi` | **Live** — UDP / pipe / TCP |
| Phone (iOS / Android stock) | — | **Not possible** with public APIs |
| Laptop / desktop stock WiFi | — | **Not possible** without CSI tool |

### Quick start — ESP32

```bash
pip install pyserial
# flash CSI firmware, plug board in, then:
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"esp32"}'
```

### Quick start — Raspberry Pi (Nexmon)

```bash
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","udp_port":5500}'
```

See [esp32.md](esp32.md) and [csi.md](csi.md) for packet formats and
wiring details. Every live frame is tagged `provenance=real_sensor_data`.

## GPU

Not required for the baseline heuristic. GPU only matters when you train and
deploy a learned spatial model (see [training.md](training.md)).

## Health metrics (v0.2)

Live adapters report `packet_loss_pct` from CSI sequence gaps. Doctor exposes `sensors_online`, `ready_for_live`, and `localization_ready` (≥ 3 sensors).
