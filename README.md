# Am the Map

*An experimental RF spatial perception platform that transforms wireless
measurements into probabilistic 3D representations of environments.*

Am the Map uses WiFi Channel State Information (CSI) to build a live,
probabilistic map of a space: occupancy probability, movement probability,
RF intensity, and spatial confidence, rendered as a decaying 3D voxel field.
It is not a camera and does not claim LiDAR-equivalent reconstruction —
every reading is explicitly tagged with where it came from (real sensor
data / simulated data / model prediction / ground truth) and whether the
model behind it has been validated.

Runs completely offline, with **zero physical hardware and zero API keys**,
via a built-in CSI simulator.

## Status

This is a working **v0.2.4** platform, built following the project's own staged
development strategy (simulator → backend → CLI → dashboard → CSI
acquisition → signal processing → occupancy → localization → voxel mapping
→ tracking → live hardware adapters → hardening) rather than attempting
every advanced feature at once.

| Piece | Status |
|---|---|
| Backend (FastAPI, acquisition/signal/ML/mapping/tracking/calibration/datasets/experiments/AI-gateway, REST+WebSocket API, SQLite) | **Built & tested** — unit tests passing; optional API auth, rate limits, path hardening |
| CLI (`am-map`, Typer+Rich) | **Built & tested** against the live backend |
| Web dashboard (React + TypeScript + Three.js + Tailwind) | **Built & verified** — type-checks clean, production build succeeds, and the actual Three.js scene code was rendered headlessly (real WebGL context via `gl`/Xvfb, not a browser) and visually confirmed to draw voxels, sensors, tracked objects, and the RF heatmap correctly — see `frontend/smoke-test/`. Not tested with real mouse/pointer interaction (drag-to-reposition, orbit controls) in an actual browser. |
| Docker Compose | Written, not run in this environment (no Docker daemon available here) |
| ESP32 / Linux CSI real-hardware adapters | **Implemented** (serial/UDP/TCP/pipe) — see [docs/hardware.md](docs/hardware.md). Phones & stock laptop WiFi cannot expose CSI. |
| Trained spatial ML model (CNN/Transformer/etc.) | **Not implemented.** Ships with a transparent baseline heuristic instead — see [docs/ml.md](docs/ml.md) |
| RF-SLAM | **Not implemented** — see [docs/rf-slam.md](docs/rf-slam.md) |
| Human pose | **Not implemented** (no validated model exists) |
| Mobile app | **Not built** — see [mobile/README.md](mobile/README.md) |

Full detail on every "not implemented" above — and why — is in `docs/`.
Nothing in this codebase pretends to have a capability it doesn't.

## Changelog

**v0.2.4** — bugfix: prune offline sensor features (false occupancy), reset map state on mode switch, calibration 404, occupancy history limit, heatmap NaN guard.

**v0.2.3** — bugfix: drag-reposition for live (non-DB) sensors, recording flush, voxel zero-radius crash, file-replay CPU spin, per-frame ingest isolation.

**v0.2.2** — bugfix: frontend REST API token headers, WebSocket accept-before-auth, sensor list packet-loss merge, session record mode guard, report model provenance, cleaner pipeline shutdown.

**v0.2.1** — bugfix: CORS preflight under API auth, WebSocket token enforcement, CLI/frontend API token support, packet-loss sync into map snapshots, clean pipeline shutdown, safer WS send error handling.

**v0.2.0** — live CSI adapters (ESP32 serial/UDP, Linux/Nexmon/PicoScenes), optional API token auth, dataset path hardening, constant-velocity tracker, calibration readiness score, AI rate limit, packet-loss from sequence gaps, richer doctor checks, dynamic model provenance flags.

**v0.1.1** — bug-scan pass. Fixed a real arbitrary file write/read
vulnerability (`POST /api/system/start`'s `recording_name` /
`replay_session_id` were used to build filesystem paths with no
validation) and the same class of path-traversal issue in dataset names;
fixed a stale-closure bug where the 3D dashboard's layer toggles and Z-slider
would silently revert a few hundred milliseconds after being changed; fixed
`AI_MODE=local` not actually restricting to local-only providers; fixed the
CLI/frontend crashing on non-JSON report formats (`--format markdown/html`);
fixed sensor drag-and-drop parallax; fixed a duplicate-WebSocket-connection
leak in development. See git history / diffs for details.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

Or run backend/frontend/CLI separately — see
[docs/installation.md](docs/installation.md).

Once running:

```bash
am-map status
am-map map --visualize
```

or open the web dashboard at http://localhost:5173 — it should show a LIVE,
streaming 3D voxel map from the simulator immediately, no setup required.

## Project layout

```
am-the-map/
├── backend/        FastAPI app: acquisition, signal, ml, mapping,
│                    tracking, calibration, datasets, experiments, ai, api
├── frontend/        React + TypeScript + Three.js dashboard
├── cli/             am-map CLI (Typer + Rich)
├── mobile/          Not built -- see mobile/README.md
├── docs/            Architecture, hardware, ML, training, privacy, etc.
├── docker-compose.yml
└── .env.example
```

## Design principles this build followed

- **Hardware-independent core.** The simulator is mandatory, not optional
  (spec §42) — the entire pipeline works with zero sensors.
- **AI-provider-independent, offline by default.** `PRIVACY_MODE=true` and
  `AI_MODE=offline` out of the box; the spatial ML pipeline never depends on
  a cloud API.
- **Never fabricate capability.** No fake trained model, no fake hardware
  driver, no fake SLAM, no fake pose estimation. Live CSI adapters (ESP32 /
  Linux tools) are real implementations; SLAM, pose, and trained nets remain
  documented non-features that fail or are omitted loudly — see
  [docs/architecture.md](docs/architecture.md).
- **Provenance everywhere.** Every map snapshot, report, and UI panel
  states whether data is real, simulated, or replayed, and whether a model
  is validated — spec §55.

## License

Apache 2.0 — see [LICENSE](LICENSE).
