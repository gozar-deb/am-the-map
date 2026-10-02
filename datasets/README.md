# datasets/

Drop raw source data here before importing it into the managed dataset
store via the API (`POST /api/datasets/import`) or CLI.

Managed datasets live under `DATA_DIR/datasets/<name>/` with subfolders:
`csi`, `sensor_metadata`, `calibration`, `ground_truth`, `labels`,
`predictions`, plus `metadata.json`.

Dataset **names** are sanitized (no path separators). Import/export
**directory paths** are resolved and validated to reduce traversal risk
(v0.2).
