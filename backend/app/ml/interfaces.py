"""
Spatial ML Engine interfaces (section 15).

`SpatialModel` is the contract every model -- baseline or learned -- must
satisfy. The architectures listed in the spec (CNN, Temporal CNN,
Transformer, Temporal Transformer, GNN, point-cloud, neural implicit) are
represented here as documented interfaces with a PyTorch/ONNX loading path,
but are intentionally NOT implemented with random/fake weights: per the
project's engineering rule, a model must not claim capability it doesn't
have. Wire a real, trained checkpoint into `TorchSpatialModel.load()` (or an
.onnx file into `ONNXSpatialModel.load()`) when one exists; until then, only
`BaselineHeuristicModel` (ml/baseline.py) is registered and it is always
labeled as a baseline, never as a validated learned model.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class ModelArchitecture(str, Enum):
    BASELINE_HEURISTIC = "baseline-heuristic"
    CNN = "cnn"
    TEMPORAL_CNN = "temporal-cnn"
    TRANSFORMER = "transformer"
    TEMPORAL_TRANSFORMER = "temporal-transformer"
    GNN = "gnn"
    POINT_CLOUD = "point-cloud"
    NEURAL_IMPLICIT = "neural-implicit"


class EstimateSource(str, Enum):
    """Attached to every prediction so the UI/API never blurs provenance."""

    SIMULATED_DATA = "simulated_data"
    MODEL_PREDICTION = "model_prediction"
    GROUND_TRUTH = "ground_truth"


@dataclass
class SpatialEstimate:
    """One model's output for one inference tick, per sensor-region."""

    occupancy_probability: float
    movement_probability: float
    position: tuple[float, float, float] | None
    confidence: float
    source: EstimateSource
    model_name: str
    is_baseline: bool = True
    notes: str | None = None


class SpatialModel(abc.ABC):
    architecture: ModelArchitecture
    name: str
    validated: bool = False  # never True until evaluated against ground truth

    @abc.abstractmethod
    def predict(self, features_by_link: dict[str, dict]) -> SpatialEstimate:
        """features_by_link: {link_id: {energy, amplitude_variance, phase_variance, temporal_delta}}"""


class TorchSpatialModel(SpatialModel):
    """Loads a PyTorch checkpoint (.pt/.pth) trained via `am-map train`.

    Not implemented until a real checkpoint + validated dataset exists --
    see docs/ml.md and docs/training.md. Raises on load so it can never be
    silently used to fabricate predictions.
    """

    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = checkpoint_path
        raise NotImplementedError(
            "No trained PyTorch spatial model is bundled with Am the Map yet. "
            "Train one with `am-map train` on a labeled dataset, then point "
            "TorchSpatialModel at the resulting checkpoint. Until then, use "
            "the baseline heuristic model."
        )

    def predict(self, features_by_link: dict[str, dict]) -> SpatialEstimate:  # pragma: no cover
        raise NotImplementedError


class ONNXSpatialModel(SpatialModel):
    """Loads an ONNX-exported model for optimized inference (section 15).
    Same status as TorchSpatialModel -- scaffold only, see docs/ml.md."""

    def __init__(self, onnx_path: str):
        self.onnx_path = onnx_path
        raise NotImplementedError(
            "No ONNX spatial model is bundled with Am the Map yet. Export a "
            "trained checkpoint to ONNX and point ONNXSpatialModel at it."
        )

    def predict(self, features_by_link: dict[str, dict]) -> SpatialEstimate:  # pragma: no cover
        raise NotImplementedError
