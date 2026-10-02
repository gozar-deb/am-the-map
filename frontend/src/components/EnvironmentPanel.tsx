import { useAppStore } from "../state/store";
import AskAI from "./AskAI";

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="border-b border-hairline px-3 py-2.5">
      <div className="label">{label}</div>
      <div className={`value-mono mt-0.5 text-xl ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}

const CHANGE_LABEL: Record<string, string> = {
  NO_BASELINE: "No baseline set",
  UNCHANGED: "Unchanged",
  CHANGED: "Changed",
  NEW_ACTIVITY: "New activity",
  REMOVED_ACTIVITY: "Removed activity",
};

export default function EnvironmentPanel() {
  const snapshot = useAppStore((s) => s.snapshot);
  const env = snapshot?.environment;

  const movementLevel = !env ? "—" : env.movement_probability > 0.5 ? "HIGH" : env.movement_probability > 0.15 ? "MED" : "LOW";
  const movementAccent = movementLevel === "HIGH" ? "text-movement" : movementLevel === "MED" ? "text-signal" : "text-ink";

  return (
    <aside className="flex w-60 shrink-0 flex-col border-l border-hairline bg-panel">
      <div className="border-b border-hairline px-3 py-2">
        <div className="label">Environment</div>
        <div className="value-mono mt-0.5 text-sm text-muted">
          {env ? `${env.bounds_m[0]}×${env.bounds_m[1]}×${env.bounds_m[2]} m` : "—"}
        </div>
      </div>

      <div className="scanlines flex-1 overflow-y-auto">
        <Stat label="Occupancy (estimate)" value={env ? String(env.occupancy_count_estimate) : "—"} />
        <Stat label="Occupancy probability" value={env ? env.occupancy_probability.toFixed(2) : "—"} />
        <Stat label="Motion" value={movementLevel} accent={movementAccent} />
        <Stat label="3D confidence" value={env ? `${Math.round(env.confidence * 100)}%` : "—"} />
        <Stat label="Change vs. baseline" value={env ? CHANGE_LABEL[env.change_state] ?? env.change_state : "—"} />
        <Stat label="Voxel resolution" value={env ? `${env.voxel_resolution_m * 100} cm` : "—"} />
      </div>

      <div className="border-t border-hairline px-3 py-2 text-[11px] text-muted">
        Model: <span className="text-ink">{env?.model ?? "—"}</span>
        <br />
        {env?.model_is_baseline && "Heuristic baseline — not a trained/validated model."}
      </div>
      <AskAI />
    </aside>
  );
}
