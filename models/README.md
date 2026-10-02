# models/

Place downloaded or exported model checkpoints here (e.g. `occupancy/`,
`localization/`). The runtime looks under `DATA_DIR/models` by default.

Today the only runnable spatial model is the in-code
`BaselineHeuristicModel` (`validated=False`, `is_baseline=True`). Torch/ONNX
interfaces exist in `backend/app/ml/interfaces.py` but no trained weights
ship with the project.

See [docs/ml.md](../docs/ml.md) and [docs/training.md](../docs/training.md).
