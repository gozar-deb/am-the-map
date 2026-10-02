"""
BaselineHeuristicModel -- the one spatial model Am the Map ships with.

Per the project's engineering rule (spec section 55/16), we do NOT ship a
"trained" CNN/Transformer/etc. with random weights and call it a spatial ML
model -- that would fabricate accuracy that doesn't exist. Instead this is an
honestly-labeled signal-deviation heuristic:

  1. Per sensor link, track a slow-moving exponential baseline of channel
     "activity" (temporal amplitude delta + variance). A live reading well
     above that baseline suggests something in the environment is
     perturbing that link (a body, a door, etc).
  2. Combine per-link activity into a room-level occupancy probability
     (probabilistic OR across links) and a coarse position estimate (an
     activity-weighted centroid of sensor positions -- NOT multilateration,
     and explicitly low-confidence with fewer than 3 active sensors).
  3. Movement probability is the smoothed frame-to-frame derivative of
     activity.

This is genuinely useful for occupancy/movement/change detection research
and is fast enough to run on a Raspberry Pi, but it is not a trained
localization or pose model -- `validated=False` and `is_baseline=True` are
always attached to its output, and docs/ml.md explains how to replace it
with a real trained model.
"""
from __future__ import annotations

import math
import time

from app.ml.interfaces import EstimateSource, ModelArchitecture, SpatialEstimate, SpatialModel


class BaselineHeuristicModel(SpatialModel):
    architecture = ModelArchitecture.BASELINE_HEURISTIC
    name = "baseline-heuristic-v1"
    validated = False

    def __init__(self, baseline_decay: float = 0.05, deviation_gain: float = 18.0):
        self.baseline_decay = baseline_decay
        self.deviation_gain = deviation_gain
        self._link_ema: dict[str, float] = {}
        self._prev_total_activity: float = 0.0
        self._movement_ema: float = 0.0
        self._sensor_positions: dict[str, tuple[float, float, float]] = {}
        self._link_to_sensor: dict[str, str] = {}
        self._smoothed_position: tuple[float, float, float] | None = None

    def configure_topology(
        self,
        sensor_positions: dict[str, tuple[float, float, float]],
        link_to_sensor: dict[str, str],
    ) -> None:
        """Called by the mapping engine whenever sensor placement changes."""
        self._sensor_positions = sensor_positions
        self._link_to_sensor = link_to_sensor

    def predict(self, features_by_link: dict[str, dict]) -> SpatialEstimate:
        """SpatialModel interface compliance -- uses topology set via
        `configure_topology`. Prefer calling `score_links` +
        `aggregate_estimate` directly when you need per-link scores too."""
        scores = self.score_links(features_by_link)
        return self.aggregate_estimate(scores, self._sensor_positions, self._link_to_sensor)

    @staticmethod
    def _raw_activity(features: dict) -> float:
        return (
            features.get("temporal_delta", 0.0) * 3.0
            + features.get("amplitude_variance", 0.0) * 2.0
            + features.get("phase_variance", 0.0) * 0.5
        )

    def score_links(self, features_by_link: dict[str, dict]) -> dict[str, float]:
        """Per-link activity score in [0, 1]; deviation above that link's own
        slow-moving baseline, squashed through 1 - e^-x."""
        scores: dict[str, float] = {}
        for link_id, features in features_by_link.items():
            raw = self._raw_activity(features)
            baseline = self._link_ema.get(link_id, raw)
            self._link_ema[link_id] = baseline * (1 - self.baseline_decay) + raw * self.baseline_decay
            deviation = max(0.0, raw - baseline)
            scores[link_id] = min(1.0, 1 - math.exp(-deviation * self.deviation_gain))
        return scores

    def aggregate_estimate(
        self,
        scores: dict[str, float],
        sensor_positions: dict[str, tuple[float, float, float]],
        link_to_sensor: dict[str, str],
    ) -> SpatialEstimate:
        if not scores:
            return SpatialEstimate(
                occupancy_probability=0.0,
                movement_probability=0.0,
                position=None,
                confidence=0.0,
                source=EstimateSource.MODEL_PREDICTION,
                model_name=self.name,
                is_baseline=True,
                notes="No active sensor links.",
            )

        # probabilistic OR across independent links
        occupancy_probability = 1.0
        for s in scores.values():
            occupancy_probability *= (1 - s)
        occupancy_probability = 1.0 - occupancy_probability

        active_links = [lid for lid, s in scores.items() if s > 0.05]
        weighted_x = weighted_y = weighted_z = 0.0
        weight_sum = 0.0
        for link_id, score in scores.items():
            sensor_id = link_to_sensor.get(link_id)
            pos = sensor_positions.get(sensor_id) if sensor_id else None
            if pos is None or score <= 0.05:
                continue
            weighted_x += pos[0] * score
            weighted_y += pos[1] * score
            weighted_z += pos[2] * score
            weight_sum += score

        position = None
        if weight_sum > 0:
            raw_position = (weighted_x / weight_sum, weighted_y / weight_sum, 1.0)
            # Exponential smoothing: a per-frame activity-weighted centroid is
            # noisy (subcarrier noise shifts which link momentarily "wins"),
            # so smooth it rather than reporting a jittery raw position --
            # this also keeps the voxel-clustering step from fragmenting one
            # slow-moving object into several transient blobs.
            if self._smoothed_position is None:
                self._smoothed_position = raw_position
            else:
                a = 0.35
                self._smoothed_position = (
                    self._smoothed_position[0] * (1 - a) + raw_position[0] * a,
                    self._smoothed_position[1] * (1 - a) + raw_position[1] * a,
                    1.0,
                )
            position = self._smoothed_position
        else:
            self._smoothed_position = None

        total_activity = sum(scores.values())
        raw_movement = abs(total_activity - self._prev_total_activity)
        self._prev_total_activity = total_activity
        self._movement_ema = self._movement_ema * 0.7 + min(1.0, raw_movement) * 0.3

        # Confidence reflects geometry, not just signal strength: you cannot
        # localize with one sensor, and this heuristic never claims high
        # certainty regardless of signal clarity.
        n_active = len(active_links)
        geometry_confidence = {0: 0.0, 1: 0.25, 2: 0.5}.get(n_active, 0.75)
        confidence = round(geometry_confidence * (0.6 + 0.4 * min(1.0, total_activity)), 3)

        notes = None
        if n_active <= 1:
            notes = "Fewer than 2 active sensors -- position estimate is not geometrically reliable."

        return SpatialEstimate(
            occupancy_probability=round(occupancy_probability, 3),
            movement_probability=round(self._movement_ema, 3),
            position=position,
            confidence=confidence,
            source=EstimateSource.MODEL_PREDICTION,
            model_name=self.name,
            is_baseline=True,
            notes=notes,
        )
