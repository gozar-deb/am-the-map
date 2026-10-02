import { useEffect, useState } from "react";
import { useAppStore } from "../state/store";

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export default function TopBar() {
  const snapshot = useAppStore((s) => s.snapshot);
  const connected = useAppStore((s) => s.connected);
  const now = useClock();

  const provenance = snapshot?.provenance ?? "none";
  const badgeClass =
    provenance === "real_sensor_data" ? "badge-real" : provenance === "replayed_data" ? "badge-replay" : "badge-simulated";
  const badgeLabel =
    provenance === "real_sensor_data" ? "Real Sensor Data" : provenance === "replayed_data" ? "Replayed Data" : "Simulated Data";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-panel px-4">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold tracking-[0.2em]">AM THE MAP</span>
        <span className="hidden text-xs text-muted sm:inline">Wireless Spatial Intelligence</span>
      </div>

      <div className="flex items-center gap-4">
        <span className={badgeClass}>{badgeLabel}</span>
        {snapshot?.environment.model_is_baseline && <span className="badge-baseline">Baseline · Unvalidated</span>}
        <div className="flex items-center gap-2">
          <span className={connected ? "live-dot" : "inline-block h-2 w-2 rounded-full bg-muted2"} />
          <span className="label">{connected ? "LIVE" : "DISCONNECTED"}</span>
        </div>
        <span className="value-mono text-sm text-muted">
          {now.toLocaleTimeString([], { hour12: false })}
        </span>
      </div>
    </header>
  );
}
