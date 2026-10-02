# Mapping (section 8, 24)

## Voxel grid

Sparse 3D grid with configurable resolution (default 0.20 m) and room bounds
(default 5×5×3 m). Each voxel stores occupancy probability, movement
probability, RF intensity, and confidence, and decays over time when not
reinforced.

## Update path

1. CSI frames → signal pipeline → features / activity scores.
2. Baseline (or plugged-in) spatial model → room-level occupancy / movement /
   coarse position.
3. Activity deposited into voxels near active links / estimated positions.
4. Connected-component clustering → detection list for the tracker.
5. Tracker (constant-velocity prediction + nearest-neighbor association)
   maintains anonymous object tracks with trails.
6. Snapshot broadcast over WebSocket (~5 Hz) with provenance tags.

## Tracker (v0.2)

- Predicts each track forward by `dt` before matching (reduces ID swaps).
- Exponentially smoothed velocity; confidence decays on missed ticks.
- Tracks age out after consecutive missed ticks.
- No identity recognition — IDs are anonymous and reassignable.

## Provenance

Every snapshot includes:

- `provenance`: data source class
- `environment.model` / `model_is_baseline` / `model_validated`
- Per-object `source` (model prediction)

## Configuration

Via `.env` / settings:

- `VOXEL_RESOLUTION_M`
- `ROOM_BOUNDS_M` (or defaults in code)

API: voxel config update endpoint when exposed; otherwise restart with new env.
