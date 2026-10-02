# RF-SLAM (section 25) — experimental, not implemented

The spec calls for an experimental RF-SLAM module:

```
RF observations → spatial features → localization → map update →
loop consistency → RF environment model
```

**This is not implemented in the current build.** Per the spec's own
instruction ("do not claim full SLAM capability until experimentally
validated"), Am the Map does not ship a module labeled RF-SLAM at all
rather than ship something partial under that name.

## What exists that's adjacent

- `MappingEngine` already does continuous map updates from streaming
  observations (the "map update" step) via the voxel grid.
- `BaselineHeuristicModel`'s position estimate is a (very coarse) stand-in
  for the "localization" step.

## What's missing for real RF-SLAM

- **Loop closure / consistency checking** — no mechanism exists to detect
  when the sensed environment revisits a previously mapped state and
  reconcile drift.
- **Joint pose-and-map optimization** — the current pipeline never
  jointly refines sensor calibration and the map; sensor positions are
  taken as given (manually placed or calibrated separately).
- **An actual RF propagation / environment model** beyond the simple
  activity-heuristic in `ml/baseline.py`.

Building this out is a legitimate, substantial research project on top of
this codebase — the acquisition/signal/mapping layers here are structured
so it can plug in as a new module under `backend/app/` (e.g.
`backend/app/rfslam/`) without changing the sensor abstraction.
