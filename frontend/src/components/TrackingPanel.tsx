import { useAppStore } from "../state/store";

export default function TrackingPanel() {
  const snapshot = useAppStore((s) => s.snapshot);
  const objects = snapshot?.objects ?? [];

  return (
    <div className="scanlines h-full overflow-y-auto p-4">
      <div className="mb-3 text-xs text-muted">
        Anonymous candidate tracks from connected-component clustering of voxel activity — not identity
        recognition (spec §33).
      </div>
      {objects.length === 0 && <div className="text-sm text-muted">No active tracks.</div>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {objects.map((o) => (
          <div key={o.id} className="border border-hairline bg-panel2 p-3">
            <div className="flex items-center justify-between">
              <span className="value-mono text-sm text-danger">{o.id}</span>
              <span className="badge-baseline">model prediction</span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-y-1 text-xs">
              <span className="text-muted">Position</span>
              <span className="value-mono text-right">
                {o.x.toFixed(2)}, {o.y.toFixed(2)}, {o.z.toFixed(2)}
              </span>
              <span className="text-muted">Velocity</span>
              <span className="value-mono text-right">{o.velocity_mps.toFixed(2)} m/s</span>
              <span className="text-muted">Confidence</span>
              <span className="value-mono text-right">{(o.confidence * 100).toFixed(0)}%</span>
              <span className="text-muted">Trail points</span>
              <span className="value-mono text-right">{o.trail.length}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
