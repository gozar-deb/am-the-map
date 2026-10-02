# Architecture

```
Sensor Network (ESP32 / CSI NIC / Nexmon / PicoScenes / simulator)
        │  CSI / RF data
        ▼
Acquisition Engine        backend/app/acquisition/
  AcquisitionInterface
    ├── SimulatedSensorAdapter   (implemented, mandatory)
    ├── FileReplayAdapter        (implemented)
    ├── ESP32Adapter             (live — serial / UDP)
    └── LinuxCSIAdapter          (live — UDP / TCP / named pipe)
        │
        ▼
Signal Processing          backend/app/signal/
  validate → sync → outlier reject → noise reduce →
  amplitude normalize → phase sanitize → subcarrier select →
  feature extract
        │
        ▼
Spatial ML Engine          backend/app/ml/
  BaselineHeuristicModel (implemented, unvalidated)
  TorchSpatialModel / ONNXSpatialModel (interfaces only, section 15)
        │
        ▼
Mapping Engine             backend/app/mapping/
  VoxelGrid (sparse, decaying) + connected-component clustering
  Tracker (constant-velocity MOT)     backend/app/tracking/
        │
        ├──────────────┐
        ▼              ▼
  Local (always on)   AI Gateway (optional)    backend/app/ai/
                         OFFLINE by default, privacy-mode gated
                         rate-limited when enabled
        │
        ▼
API / WebSocket             backend/app/api/
  Optional API_TOKEN auth (off by default for local research)
        │
   ┌────┼────┐
   ▼    ▼    ▼
  CLI  Web  (Mobile — not yet built, see mobile/README.md)
```

## Runtime wiring

`backend/app/core/runtime.py` is the only place that connects these layers
at runtime:

1. An **ingest loop** pulls `CSIFrame`s from whichever `AcquisitionInterface`
   is active and feeds them to `MappingEngine.ingest()`, which runs the
   signal pipeline, updates per-link activity scores, and (if recording)
   appends the frame to a `.jsonl` file.
2. A **tick loop** (5 Hz) calls `MappingEngine.tick()`, which computes the
   room-level spatial estimate, updates the voxel grid, clusters it into
   candidate objects, updates the tracker, decays the grid, and broadcasts
   the resulting snapshot to every WebSocket subscriber.

Every snapshot carries a `provenance` field
(`simulated_data` / `real_sensor_data` / `replayed_data`) and every model
output is tagged `model_is_baseline` / `model_validated` (read from the
active model instance) so the UI, CLI, and reports never blur what's real,
simulated, predicted, or ground truth (spec §55).

## Acquisition modes

| Mode | Adapter | Provenance |
|------|---------|------------|
| `simulated` | SimulatedSensorAdapter | `simulated_data` |
| `file_replay` | FileReplayAdapter | `replayed_data` |
| `esp32` | ESP32Adapter (serial or UDP) | `real_sensor_data` |
| `linux_csi` | LinuxCSIAdapter (UDP/TCP/pipe) | `real_sensor_data` |

Start live hardware with connection parameters on
`POST /api/system/start` (see [api.md](api.md), [hardware.md](hardware.md)).

## Why a "baseline heuristic" instead of a neural model

Section 15 of the spec calls for CNN/Transformer/GNN/point-cloud/neural
implicit architectures. Those are represented as typed interfaces in
`ml/interfaces.py` with a PyTorch/ONNX loading path, but **no untrained or
random-weight network is shipped as if it were a working model**. The
platform runs a transparent signal-deviation heuristic
(`BaselineHeuristicModel`) labeled `validated=False` / `is_baseline=True`.
See [ml.md](ml.md) and [training.md](training.md) for how to replace it.

## Security layers (v0.2)

- **Optional API token** (`API_TOKEN`) — when set, protects all routes except
  `/`, `/api/status`, `/api/system/doctor`, and OpenAPI docs.
- **Dataset path hardening** — `sanitize_id` for names; `safe_resolve_dir`
  for import/export directories.
- **AI rate limit** — configurable requests/minute on `/api/ai/ask`.
- **Privacy mode / offline AI** — still the default; no external calls
  without explicit opt-in.

## Tracker

The tracker uses constant-velocity prediction before nearest-neighbor
association, exponentially smoothed velocity, and confidence decay on
missed ticks. Tracks are anonymous IDs (no identity recognition claim).
