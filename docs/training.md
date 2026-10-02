# Training (section 41)

`am-map train` currently prints an explanation rather than training
anything, because there is no trainable checkpoint bundled with Am the Map
— see [ml.md](ml.md) for why.

## Path to real training

1. **Collect labeled data.**
   - `am-map dataset create <name>` sets up the standard layout
     (`csi/`, `sensor_metadata/`, `calibration/`, `ground_truth/`,
     `labels/`, `predictions/`, `metadata.json`) under
     `backend/data/datasets/<name>/`.
   - Record sessions with real (or simulated) sensors:
     `am-map record <name>` writes raw `CSIFrame`s to
     `backend/data/recordings/<session_id>.jsonl` — copy/link these into a
     dataset's `csi/` folder.
   - Add ground truth (section 26-27) — e.g. a LiDAR/camera-derived
     position track, or manually annotated occupancy — into
     `ground_truth/` and `labels/`.

2. **Implement a trainer.** There is no bundled training loop (it depends
   entirely on which architecture and label format you choose). A typical
   PyTorch loop would:
   - Load a dataset via `app/datasets/service.py`'s layout.
   - Featurize with `app/signal/pipeline.py::SignalProcessingPipeline` so
     inference-time features match training-time features exactly.
   - Train against `ground_truth/` labels.
   - Export a checkpoint.

3. **Wire the checkpoint in.**
   - Point `TorchSpatialModel(checkpoint_path=...)` (or
     `ONNXSpatialModel` after exporting to ONNX) at the file —
     remove the `NotImplementedError` guard once you've verified it loads.
   - Register it via `ml/registry.py` with real `accuracy_metrics` and
     `validated=True` — never mark a model validated without an actual
     evaluation against `ground_truth/`.
   - Swap `ml/registry.py::get_active_model()` to return it (behind a
     config flag is recommended, so you can A/B against the baseline).

4. **Evaluate** (section 27) — position error, occupancy accuracy,
   precision/recall/F1, tracking error — before calling it validated.

## Config example (matches the spec's `am-map train` config shape)

```yaml
model:
  architecture: transformer

dataset:
  path: datasets/room01

training:
  epochs: 100
  batch_size: 32
  learning_rate: 0.0001
```

`am-map train --config path/to/this.yaml` reads and echoes this today;
hooking it up to an actual training loop is the integration work described
above.
