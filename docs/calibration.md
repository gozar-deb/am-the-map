# Calibration (section 22)

`am-map calibrate` / `POST /api/calibration/run` / the dashboard "Run
calibration" control samples the **already running** acquisition + mapping
pipeline for a configurable window (default 10 s), computes real stability
metrics from observed data, and stores an empty-room baseline for change
detection (section 23).

## Metrics (all derived from live samples — never placeholders)

- **Signal stability %** — inverse of occupancy-probability variance across
  the window.
- **Sensor synchronization %** — average fraction of sensors online.
- **Packet quality %** — `100 - average packet loss %` across sensors
  (live adapters report loss from CSI sequence gaps).
- **Calibration confidence %** — weighted combination (40 / 30 / 30).

## Readiness (v0.2)

The response also includes:

| Field | Meaning |
|-------|---------|
| `ready_for_live` | Confidence ≥ 50%, ≥ 1 online sensor, signal not critically unstable |
| `online_sensors_observed` | Max online sensors seen during the window |
| `warnings` | e.g. fewer than 3 sensors (localization under-constrained), unstable signal, high packet loss |

If no data was collected (pipeline not running), the endpoint returns an
explicit error rather than a fabricated result.

## Applying a saved profile

`POST /api/calibration/profiles/{id}/apply` reloads a previously saved
baseline without re-running the sampling window — useful for restoring the
"expected empty room" state after a restart.

## Recommended workflow

1. Start acquisition (`simulated`, `esp32`, or `linux_csi`).
2. Clear the room.
3. Run calibration for 10–30 s.
4. Check `ready_for_live` and any `warnings`.
5. Proceed with occupancy / tracking experiments.
