# API Reference

Interactive docs: `http://localhost:8000/docs` (FastAPI auto-generated
OpenAPI). Base URL defaults to `http://localhost:8000`.

## Authentication (optional)

When `API_TOKEN` is set in `.env`, most endpoints require:

```http
Authorization: Bearer <token>
# or
X-API-Token: <token>
```

Always open (no token required): `/`, `/api/status`, `/api/system/doctor`,
`/docs`, `/redoc`, `/openapi.json`.

WebSocket clients pass `?token=<token>` when auth is enabled.

## System

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/status` | Acquisition mode, recording flag, latest map snapshot |
| GET | `/api/system/doctor` | Dependency, DB, sensor, model, calibration, auth checks |
| GET | `/api/system/config` | AI mode, privacy, voxel resolution, bounds |
| GET | `/api/system/scan` | Known sensors + live health |
| POST | `/api/system/start` | Start pipeline (see body below) |
| POST | `/api/system/stop` | Stop acquisition |

### `POST /api/system/start` body

```json
{
  "mode": "simulated | esp32 | linux_csi | file_replay",
  "recording_name": "optional-session-id",
  "replay_session_id": "required for file_replay",
  "replay_speed": 1.0,
  "port": "/dev/ttyUSB0",
  "baud": 921600,
  "udp_host": "0.0.0.0",
  "udp_port": 5005,
  "tcp_host": "127.0.0.1",
  "tcp_port": 9000,
  "source_path": "/tmp/csi.log",
  "sensor_id": "ESP32-01",
  "interface": "wlan0"
}
```

Hardware fields apply only to `esp32` / `linux_csi`. See
[hardware.md](hardware.md), [esp32.md](esp32.md), [csi.md](csi.md).

## Sensors / sessions / maps / occupancy / tracking

CRUD and query endpoints under `/api/sensors`, `/api/sessions`, `/api/maps`,
`/api/occupancy`, `/api/tracking`. Map snapshots include `provenance`,
`model_is_baseline`, and `model_validated`.

## Calibration

| Method | Path |
|--------|------|
| POST | `/api/calibration/run` |
| GET | `/api/calibration/profiles` |
| POST | `/api/calibration/profiles/{id}/apply` |

Response includes `ready_for_live`, `warnings`, and metric percentages.
See [calibration.md](calibration.md).

## AI

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/ai/status` | Mode, privacy, configured providers |
| POST | `/api/ai/ask` | Rate-limited; blocked when Privacy Mode / OFFLINE |

## Datasets / models / experiments / reports

`/api/datasets`, `/api/models`, `/api/experiments`, `/api/reports` — see
OpenAPI for full schemas. Dataset import/export paths are validated.

## WebSockets

| Path | Payload |
|------|---------|
| `/ws/map` | Full map snapshot (~5 Hz) |
| `/ws/csi` | Per-frame CSI preview |
| `/ws/sensors` | Sensor health (same snapshot bus) |
| `/ws/tracking` | Tracked objects (same snapshot bus) |

Auth: append `?token=<API_TOKEN>` when enabled.
