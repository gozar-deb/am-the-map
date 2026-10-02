import { useAppStore } from "../state/store";

export default function SensorPanel() {
  const snapshot = useAppStore((s) => s.snapshot);
  const selectedSensorId = useAppStore((s) => s.selectedSensorId);
  const setSelectedSensor = useAppStore((s) => s.setSelectedSensor);

  const sensors = snapshot?.sensors ?? [];
  const onlineCount = sensors.filter((s) => s.status === "online").length;

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-hairline bg-panel">
      <div className="border-b border-hairline px-3 py-2">
        <div className="label">Sensor Network</div>
        <div className="value-mono mt-0.5 text-lg">
          {onlineCount}<span className="text-muted"> / {sensors.length} online</span>
        </div>
      </div>

      <div className="scanlines flex-1 overflow-y-auto">
        {sensors.length === 0 && <div className="p-3 text-xs text-muted">No sensors yet.</div>}
        {sensors.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedSensor(s.id === selectedSensorId ? null : s.id)}
            className={`block w-full border-b border-hairline px-3 py-2 text-left transition-colors hover:bg-panel2 ${
              s.id === selectedSensorId ? "bg-panel2" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full ${s.status === "online" ? "bg-signal" : "bg-muted2"}`}
              />
              <span className="value-mono text-sm">{s.id}</span>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-x-2 text-[11px] text-muted">
              <span>CSI</span>
              <span className="value-mono text-right text-ink">{s.csi_hz != null ? `${s.csi_hz.toFixed(0)}Hz` : "—"}</span>
              <span>Pos</span>
              <span className="value-mono text-right text-ink">
                {s.position.map((v) => v.toFixed(1)).join(", ")}
              </span>
            </div>
          </button>
        ))}
      </div>

      <div className="border-t border-hairline px-3 py-2 text-[11px] text-muted">
        <div className="flex justify-between">
          <span>CSI rate</span>
          <span className="value-mono text-ink">{snapshot?.environment.avg_csi_hz ?? 0} Hz</span>
        </div>
        <div className="flex justify-between">
          <span>Links</span>
          <span className="value-mono text-ink">{sensors.length}</span>
        </div>
      </div>
    </aside>
  );
}
