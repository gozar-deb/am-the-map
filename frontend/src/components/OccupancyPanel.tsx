import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAppStore } from "../state/store";
import type { FindingInfo } from "../types";

export default function OccupancyPanel() {
  const snapshot = useAppStore((s) => s.snapshot);
  const env = snapshot?.environment;
  const [findings, setFindings] = useState<FindingInfo[]>([]);

  useEffect(() => {
    const load = () => api.occupancyHistory(30).then(setFindings).catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="scanlines flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <BigStat label="Occupancy estimate" value={env ? String(env.occupancy_count_estimate) : "—"} />
        <BigStat label="Probability" value={env ? env.occupancy_probability.toFixed(2) : "—"} />
        <BigStat label="Movement probability" value={env ? env.movement_probability.toFixed(2) : "—"} />
        <BigStat label="Confidence" value={env ? `${Math.round(env.confidence * 100)}%` : "—"} />
      </div>

      <div className="text-xs text-muted">
        Estimated by connected-component clustering of voxel occupancy probability above threshold — a
        heuristic, not a validated head-count model (spec §16, §55).
      </div>

      <div>
        <div className="label mb-2">Change events (vs. calibration baseline)</div>
        <div className="border border-hairline">
          {findings.length === 0 && <div className="p-3 text-sm text-muted">No change events recorded yet. Run a calibration baseline first.</div>}
          {findings.map((f) => (
            <div key={f.id} className="flex items-center justify-between border-b border-hairline px-3 py-2 text-xs last:border-b-0">
              <span className="value-mono text-signal">{f.kind}</span>
              <span className="text-muted">{f.description}</span>
              <span className="value-mono">{(f.confidence * 100).toFixed(0)}%</span>
              <span className="text-muted">{new Date(f.created_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BigStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-hairline bg-panel2 p-3">
      <div className="label">{label}</div>
      <div className="value-mono mt-1 text-2xl">{value}</div>
    </div>
  );
}
