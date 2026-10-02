# Privacy & Security (section 43)

## Defaults

- `PRIVACY_MODE=true` and `AI_MODE=offline` out of the box (see
  `.env.example`). No CSI, features, or map data ever leaves the machine
  unless you explicitly change both.
- The simulator runs by default — no real sensing occurs unless you start
  an ESP32/Linux CSI adapter yourself.
- `Settings.external_ai_allowed()` (`backend/app/core/config.py`) is the
  single choke point every AI request passes through. Privacy Mode and
  OFFLINE mode both short-circuit it before any network call is attempted.

## Optional API authentication (v0.2)

Set `API_TOKEN` in `.env` to require a bearer token on all API routes except
`/`, `/api/status`, `/api/system/doctor`, and OpenAPI docs.

```http
Authorization: Bearer <token>
# or
X-API-Token: <token>
```

WebSocket clients pass `?token=<token>`. Leave `API_TOKEN` empty for open
local research use.

## AI rate limiting

`AI_RATE_LIMIT_PER_MINUTE` (default 30) limits `/api/ai/ask` to reduce
accidental cloud spend when external AI is enabled.

## Path safety

Dataset names and recording/session IDs are sanitized (`sanitize_id`).
Import/export directory paths are resolved and validated
(`safe_resolve_dir`) to reduce traversal risk.

## What's local-only by default

- Signal processing, the baseline spatial ML model, voxel mapping, and
  tracking — always local, no network calls, no API keys required.
- Recordings (`data/recordings/*.jsonl`) and the SQLite database
  (`data/am_the_map.db`) stay on disk.

## What requires explicit opt-in

- Any AI Gateway request (`/api/ai/ask`) — disabled by Privacy Mode/OFFLINE
  by default; even when enabled, only a structured summary is sent, never
  raw CSI, unless you pass `include_raw_features: true` explicitly per
  request.
- Real hardware acquisition (ESP32/Linux CSI) — off unless you start it.
- API authentication — off until `API_TOKEN` is set.

## Data retention & deletion

- `DELETE /api/sessions/{id}` removes both the database row and the
  recording file.
- `DELETE /api/sensors/{id}` removes a registered sensor.
- `DELETE /api/models/{name}` removes a non-baseline model record.
- There is no telemetry to Anthropic, the project maintainers, or anyone
  else built into this codebase.

## Not designed for covert surveillance

- The web dashboard's top bar always shows a LIVE indicator and data
  provenance badge whenever the pipeline is running — there is no "hidden"
  mode.
- `am-map status` / `am-map doctor` always reflect the true
  acquisition/AI state; there is no silent-background-recording feature.

If you build on this platform for a use case involving other people's
spaces, follow applicable wiretapping/surveillance and data-protection law
in your jurisdiction — this is general information, not legal advice.
