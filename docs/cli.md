# CLI Reference (section 4)

```bash
pip install -e ./cli
export AM_MAP_API_URL=http://localhost:8000   # if not default
# If API_TOKEN is set on the server, the CLI must send it too
# (configure via environment or future --token flag as implemented)
```

## Common commands

```bash
am-map status
am-map doctor
am-map sensors list
am-map calibrate --duration 10
am-map record <name> --duration 20
am-map sessions
am-map replay <session-id>
am-map map --visualize
am-map export --format markdown --out report.md
am-map ai "What is the current occupancy?"
am-map models list
am-map dataset list
```

Start/stop of acquisition modes is primarily via the HTTP API
(`POST /api/system/start` with `mode` and hardware params). The CLI status
and doctor commands reflect live adapter state, calibration readiness, and
auth configuration when the backend is running.

See also [installation.md](installation.md) and [api.md](api.md).
