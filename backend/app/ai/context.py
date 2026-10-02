"""Builds the structured text context handed to the optional LLM (section 20).
Default behaviour sends only the room-level summary -- occupancy, movement,
confidence, sensors, tracked objects, change state -- never raw CSI, unless
the caller explicitly sets include_raw_features=True."""
from __future__ import annotations

import json


def build_context(snapshot: dict, include_raw_features: bool = False, raw_features: dict | None = None) -> str:
    env = snapshot.get("environment", {})
    sensors = snapshot.get("sensors", [])
    objects = snapshot.get("objects", [])

    lines = [
        "You are given a structured summary of a probabilistic RF spatial map "
        "produced by a WiFi CSI sensing platform (Am the Map). This is NOT a "
        "camera feed and NOT LiDAR-equivalent -- it is a coarse, probabilistic "
        "estimate from a baseline heuristic model. Never state anything with "
        "more certainty than the given confidence values imply.",
        "",
        f"Data provenance: {snapshot.get('provenance')}",
        f"Model: {env.get('model')} (baseline={env.get('model_is_baseline')}, validated={env.get('model_validated')})",
        f"Environment bounds (m): {env.get('bounds_m')}, voxel resolution: {env.get('voxel_resolution_m')} m",
        f"Occupancy probability: {env.get('occupancy_probability')}",
        f"Estimated candidate object count: {env.get('occupancy_count_estimate')}",
        f"Movement probability: {env.get('movement_probability')}",
        f"Overall confidence: {env.get('confidence')}",
        f"Change state vs. baseline: {env.get('change_state')}",
        f"Average CSI rate: {env.get('avg_csi_hz')} Hz",
        "",
        f"Sensors ({len(sensors)}):",
    ]
    for s in sensors:
        lines.append(f"  - {s['id']}: status={s['status']} pos={s['position']} csi_hz={s['csi_hz']}")

    lines.append("")
    lines.append(f"Tracked candidate objects ({len(objects)}):")
    for o in objects:
        lines.append(
            f"  - {o['id']}: pos=({o['x']}, {o['y']}, {o['z']}) velocity={o['velocity_mps']} m/s "
            f"confidence={o['confidence']} source={o['source']}"
        )

    if include_raw_features and raw_features:
        lines.append("")
        lines.append("Raw per-link processed CSI features (explicitly opted in):")
        lines.append(json.dumps(raw_features, indent=2)[:4000])

    return "\n".join(lines)
