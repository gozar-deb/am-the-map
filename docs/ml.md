# Spatial ML Engine (section 15-16)

## What ships today: `BaselineHeuristicModel`

`backend/app/ml/baseline.py`. Per sensor **link** (a sensor's observed CSI
channel), it:

1. Computes a raw "activity" score from processed CSI features
   (`temporal_delta`, `amplitude_variance`, `phase_variance`).
2. Tracks a slow exponential-moving-average baseline of that score per link.
3. Reports deviation-above-baseline, squashed through `1 - e^-x`, as a
   `[0, 1]` activity score — this is what shows up as **RF intensity** in
   the heatmap.

Room-level estimates combine link scores:

- **Occupancy probability** — probabilistic OR across links
  (`1 - Π(1 - score_i)`).
- **Position estimate** — an activity-weighted centroid of sensor
  positions, exponentially smoothed over time. **This is not
  multilateration.** With fewer than 2 active sensors it's not
  geometrically meaningful at all (confidence is capped accordingly), and
  even with 3+ sensors, a *single* centroid cannot separate multiple
  simultaneous objects — it will smear toward a point between them.
- **Movement probability** — smoothed frame-to-frame derivative of total
  activity.
- **Confidence** — a function of *sensor geometry* (how many sensors are
  actually contributing), not just signal clarity. It is deliberately
  conservative.

## Known limitation: occupancy-count overcounting

The "occupancy count" shown in the UI/CLI comes from connected-component
clustering of voxels with occupancy probability above a threshold
(`MappingEngine._cluster_voxels`). Because the position estimate is a
single noisy centroid, its trail across a few ticks can occasionally
fragment into more than one cluster, or transient per-link noise can create
a small stray blob near a sensor. **Treat the count as a rough estimate,
not a validated head-count** — this is stated directly in the API response
(`/api/occupancy`) and in every generated report.

## Architecture interfaces for real models (not implemented)

`backend/app/ml/interfaces.py` defines `TorchSpatialModel` and
`ONNXSpatialModel` matching the architectures the spec calls for (CNN,
Temporal CNN, Transformer, Temporal Transformer, GNN, point-cloud, neural
implicit). Both intentionally **raise `NotImplementedError` on
construction** rather than run with random weights — see
[training.md](training.md) for how to actually fill these in once you have
a labeled dataset.

## Human pose (section 16)

Not implemented — no trained pose model exists, so none is claimed. The
"Pose skeleton" layer toggle exists in the dashboard as a UI hook but
renders nothing (and says so) until a real, validated pose model is wired
in.

## Snapshot tags

Map snapshots expose `environment.model`, `model_is_baseline`, and `model_validated` from the active model instance (not hard-coded constants).
