# simulator/

The mandatory CSI simulator (spec §42) is implemented as
`backend/app/acquisition/simulated.py` (`SimulatedSensorAdapter`).

It generates synthetic CSI-like amplitude/phase driven by simulated moving
objects plus noise so the full pipeline (signal → ML → voxels → tracker →
dashboard) works with **zero physical hardware**.

- Auto-starts when `SIMULATOR_ENABLED=true` (default).
- Provenance tag: `simulated_data`.
- Switch away with `POST /api/system/start` using `mode=esp32`,
  `linux_csi`, or `file_replay`.

See [docs/hardware.md](../docs/hardware.md) and [docs/architecture.md](../docs/architecture.md).
