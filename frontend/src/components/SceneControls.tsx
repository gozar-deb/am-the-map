import { useAppStore } from "../state/store";
import type { LayerKey } from "../types";

const LAYER_LABELS: [LayerKey, string][] = [
  ["sensors", "Sensors"],
  ["environment", "Environment"],
  ["occupancy", "Occupancy"],
  ["movement", "Movement"],
  ["rf_field", "RF field"],
  ["confidence", "Confidence"],
  ["historical_trails", "Historical trails"],
  ["pose_skeleton", "Pose skeleton"],
];

const Z_PRESETS = [0.2, 0.5, 1.0, 1.5, 2.0];

export default function SceneControls() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const zSlice = useAppStore((s) => s.zSlice);
  const setZSlice = useAppStore((s) => s.setZSlice);
  const viewMode = useAppStore((s) => s.viewMode);
  const setViewMode = useAppStore((s) => s.setViewMode);

  return (
    <>
      <div className="pointer-events-auto absolute left-3 top-3 w-40 rounded-sm border border-hairline bg-panel/90 p-2 backdrop-blur-sm">
        <div className="label mb-1.5">Layers</div>
        {LAYER_LABELS.map(([key, label]) => (
          <label key={key} className="flex cursor-pointer items-center gap-2 py-0.5 text-xs text-ink">
            <input
              type="checkbox"
              checked={layers[key]}
              onChange={() => toggleLayer(key)}
              className="h-3 w-3 accent-signal"
            />
            {label}
            {key === "pose_skeleton" && layers.pose_skeleton && (
              <span className="text-[9px] text-muted">(no model)</span>
            )}
          </label>
        ))}
      </div>

      <div className="pointer-events-auto absolute right-3 top-3 flex gap-1 rounded-sm border border-hairline bg-panel/90 p-1 backdrop-blur-sm">
        {(["orbit", "top", "first_person"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setViewMode(v)}
            className={`rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-wide ${
              viewMode === v ? "bg-signal text-void" : "text-muted hover:text-ink"
            }`}
          >
            {v === "first_person" ? "1st Person" : v}
          </button>
        ))}
      </div>

      {layers.rf_field && (
        <div className="pointer-events-auto absolute bottom-3 left-1/2 w-72 -translate-x-1/2 rounded-sm border border-hairline bg-panel/90 p-2 backdrop-blur-sm">
          <div className="mb-1 flex items-center justify-between">
            <span className="label">RF heatmap plane · Z</span>
            <span className="value-mono text-xs text-signal">{zSlice.toFixed(1)} m</span>
          </div>
          <input
            type="range"
            min={0.1}
            max={2.5}
            step={0.05}
            value={zSlice}
            onChange={(e) => setZSlice(parseFloat(e.target.value))}
            className="w-full accent-signal"
          />
          <div className="mt-1 flex justify-between">
            {Z_PRESETS.map((z) => (
              <button
                key={z}
                onClick={() => setZSlice(z)}
                className="font-mono text-[10px] text-muted hover:text-signal"
              >
                {z}m
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
