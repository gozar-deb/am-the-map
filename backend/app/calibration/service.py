"""
Guided calibration workflow (section 22) and environment baseline (section 23).

Samples the running pipeline, computes real stability metrics, stores an
empty-room baseline for change detection, and reports readiness for live use.
"""
from __future__ import annotations

import asyncio
import statistics
import time

from app.mapping.engine import MappingEngine


async def run_calibration(engine: MappingEngine, duration_s: float = 10.0, poll_interval: float = 0.5) -> dict:
    samples: list[dict] = []
    t0 = time.time()
    while time.time() - t0 < duration_s:
        await asyncio.sleep(poll_interval)
        if engine.last_snapshot:
            samples.append(engine.last_snapshot)

    if not samples:
        return {
            "error": "No data collected during calibration window. Is a sensor "
            "source running? Start the simulator or connect a real sensor first.",
            "ready_for_live": False,
        }

    occ_values = [s["environment"]["occupancy_probability"] for s in samples]
    stability_penalty = (statistics.pstdev(occ_values) if len(occ_values) > 1 else 0.0) * 4
    signal_stability_pct = round(max(0.0, min(100.0, 100 * (1 - stability_penalty))), 1)

    online_ratios = []
    packet_losses = []
    max_online = 0
    for snap in samples:
        sensors = snap["sensors"]
        if sensors:
            online = len([s for s in sensors if s["status"] == "online"])
            max_online = max(max_online, online)
            online_ratios.append(online / len(sensors))
            packet_losses.extend(s.get("packet_loss_pct", 0.0) for s in sensors)
    sensor_sync_pct = round(100 * (sum(online_ratios) / len(online_ratios)), 1) if online_ratios else 0.0
    packet_quality_pct = (
        round(max(0.0, 100 - (sum(packet_losses) / len(packet_losses))), 1) if packet_losses else 0.0
    )

    calibration_confidence_pct = round(
        signal_stability_pct * 0.4 + sensor_sync_pct * 0.3 + packet_quality_pct * 0.3, 1
    )

    warnings: list[str] = []
    if max_online < 3:
        warnings.append(
            f"Only {max_online} online sensor(s) observed. "
            "3+ sensors recommended for geometrically meaningful localization."
        )
    if signal_stability_pct < 60:
        warnings.append("Signal unstable during calibration — try a quieter empty room.")
    if packet_quality_pct < 70:
        warnings.append("High packet loss during calibration — check sensor links.")

    ready = calibration_confidence_pct >= 50 and max_online >= 1 and not (
        signal_stability_pct < 40
    )

    baseline_snapshot = {
        "occupancy_probability": round(statistics.fmean(occ_values), 4),
        "sample_count": len(samples),
        "captured_at": time.time(),
        "provenance": samples[-1]["provenance"],
        "online_sensors": max_online,
    }
    engine.apply_calibration_baseline(baseline_snapshot)

    return {
        "signal_stability_pct": signal_stability_pct,
        "sensor_synchronization_pct": sensor_sync_pct,
        "packet_quality_pct": packet_quality_pct,
        "calibration_confidence_pct": calibration_confidence_pct,
        "samples_collected": len(samples),
        "online_sensors_observed": max_online,
        "warnings": warnings,
        "ready_for_live": ready,
        "baseline_snapshot": baseline_snapshot,
    }
