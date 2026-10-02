# examples/

Minimal end-to-end walkthroughs against a running backend.

## Simulator path

```bash
# 1. Backend already running with the simulator auto-started.
am-map status                                   # confirm it's LIVE
am-map sensors list                             # NODE-01/02/03 online

# 2. Calibrate an empty-room baseline.
am-map calibrate --duration 10

# 3. Record a short session.
am-map record demo-session --duration 20

# 4. Inspect / replay.
am-map sessions
am-map replay <session-id>

# 5. Export a report.
am-map export --format markdown --out demo-report.md

# 6. Ask the (offline-by-default) AI gateway — will explain that Privacy
#    Mode is blocking it unless you've configured a provider.
am-map ai "What's happening in the room right now?"
```

## Live ESP32 path

```bash
pip install pyserial
# Flash CSI firmware, plug board in, then:
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"esp32"}'

am-map doctor    # sensors_online, ready_for_live
am-map calibrate --duration 15
```

## Live Raspberry Pi / Nexmon path

```bash
curl -X POST http://localhost:8000/api/system/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"linux_csi","udp_port":5500,"sensor_id":"RPI-01"}'
```

See [docs/research.md](../docs/research.md), [docs/hardware.md](../docs/hardware.md),
and [docs/installation.md](../docs/installation.md).
