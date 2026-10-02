# ESP32 / ESP32-S3 CSI Acquisition

**Status: implemented** (`backend/app/acquisition/esp32.py`).

Live CSI from ESP32 / ESP32-S3 boards running CSI-capable firmware
(typically a fork of [ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool)).

## Transports

| Transport | How to start |
|-----------|----------------|
| USB serial | `POST /api/system/start {"mode":"esp32","port":"/dev/ttyUSB0","baud":921600}` |
| USB serial (auto-detect) | `{"mode":"esp32"}` — picks the first CP210x/CH340/FTDI port |
| UDP (multi-board) | `{"mode":"esp32","udp_port":5005}` |

Install serial support once:

```bash
pip install pyserial
```

## Firmware

1. Flash CSI-capable firmware to the ESP32 / ESP32-S3.
2. Configure it to emit CSI over serial (default) or UDP.
3. Preferred line formats (auto-detected):

```json
{"sensor_id":"NODE-01","amplitude":[1.2,1.1,...],"phase":[0.1,-0.2,...],"rssi":-48,"seq":12}
```

or classic ESP32-CSI-Tool CSV rows containing a `CSI_DATA` field, or plain
`amp1 amp2 ... | phase1 phase2 ...` lines.

## CLI / API examples

```bash
# Serial
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"esp32","port":"/dev/ttyUSB0"}'

# UDP from several boards
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"esp32","udp_port":5005,"sensor_id":"ROOM-A"}'
```

Every frame is tagged `provenance=real_sensor_data`. If the port cannot be
opened, the API returns HTTP 400 with a clear error — it never invents data.

## Placement tips

- Mount sensors at a consistent height (e.g. Z ≈ 2.2 m).
- 3+ sensors give a geometrically meaningful position estimate with the
  baseline model; 1–2 sensors still support occupancy / change detection.
