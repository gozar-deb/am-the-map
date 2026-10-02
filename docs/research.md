# Using Am the Map for research

## What the platform gives you today

- **Provenance on every value** — `simulated_data` / `real_sensor_data` /
  `replayed_data`, plus `model_is_baseline` / `model_validated`.
- **Live CSI paths** — ESP32 (serial/UDP) and Linux CSI tools (Nexmon,
  PicoScenes, Atheros) via `mode=esp32` / `mode=linux_csi`.
- **Simulator** — mandatory offline path for algorithm work without hardware.
- **Recording / replay** — `.jsonl` sessions with original relative timing.
- **Calibration baselines** — empty-room snapshots with readiness metrics.
- **Transparent baseline spatial model** — not a fake neural net.
- **Optional API auth + AI rate limits** for shared lab machines.

## Suggested research workflow

1. Develop algorithms against the simulator (`mode=simulated`).
2. Calibrate and record controlled sessions.
3. Replay sessions while iterating on signal / ML / mapping code.
4. Connect real CSI hardware when available; same pipeline, different
   provenance tag.
5. Export reports and datasets for paper artifacts.

## What not to claim

- Do not report the baseline heuristic as a validated localization model.
- Do not claim phone/laptop stock WiFi CSI — it is not available.
- Do not claim RF-SLAM or human pose (not implemented).

## Reproducibility tips

- Pin `VOXEL_RESOLUTION_M` and room bounds in `.env`.
- Store sensor layout (positions) with each experiment.
- Keep firmware version / CSI tool name in session notes.
- Prefer `file_replay` when comparing algorithm versions on the same data.
