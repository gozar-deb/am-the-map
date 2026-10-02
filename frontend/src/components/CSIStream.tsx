import { useMemo, useState } from "react";
import { useAppStore } from "../state/store";

function Sparkline({ values, color, height = 90 }: { values: number[]; color: string; height?: number }) {
  const width = 600;
  const path = useMemo(() => {
    if (values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * width;
        const y = height - ((v - min) / range) * height;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [values, height]);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-24 w-full" preserveAspectRatio="none">
      <line x1={0} y1={height} x2={width} y2={height} stroke="#1e2830" strokeWidth={1} />
      {path && <path d={path} fill="none" stroke={color} strokeWidth={1.5} />}
    </svg>
  );
}

export default function CSIStream() {
  const csiHistory = useAppStore((s) => s.csiHistory);
  const linkIds = Object.keys(csiHistory);
  const [selectedLink, setSelectedLink] = useState<string | null>(null);
  const [subcarrier, setSubcarrier] = useState(0);
  const [source, setSource] = useState<"processed" | "raw">("processed");

  const link = selectedLink ?? linkIds[0];
  const frames = link ? csiHistory[link] ?? [] : [];
  const nSubcarriers = frames.length ? (frames[frames.length - 1].amplitude?.length ?? 0) : 0;
  const sc = Math.min(subcarrier, Math.max(0, nSubcarriers - 1));

  const amplitudeSeries = frames.map((f) => {
    const arr = source === "raw" ? f.raw_amplitude : f.amplitude;
    return arr?.[sc] ?? 0;
  });
  const phaseSeries = frames.map((f) => f.phase?.[sc] ?? 0);
  const latest = frames[frames.length - 1];

  return (
    <div className="scanlines flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-muted">
          Link
          <select
            value={link ?? ""}
            onChange={(e) => setSelectedLink(e.target.value)}
            className="border border-hairline bg-panel2 px-2 py-1 font-mono text-xs text-ink"
          >
            {linkIds.length === 0 && <option>—</option>}
            {linkIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs text-muted">
          Subcarrier
          <input
            type="range"
            min={0}
            max={Math.max(0, nSubcarriers - 1)}
            value={sc}
            onChange={(e) => setSubcarrier(parseInt(e.target.value))}
            className="accent-signal"
          />
          <span className="value-mono w-8 text-ink">{sc}</span>
        </label>

        <label className="flex items-center gap-2 text-xs text-muted">
          Antenna
          <select disabled className="border border-hairline bg-panel2 px-2 py-1 font-mono text-xs text-muted">
            <option>0 (single-antenna sim)</option>
          </select>
        </label>

        <div className="ml-auto flex overflow-hidden rounded-sm border border-hairline">
          {(["raw", "processed"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className={`px-2 py-1 font-mono text-[11px] uppercase ${
                source === s ? "bg-signal text-void" : "text-muted hover:text-ink"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {!link && <div className="text-sm text-muted">Waiting for CSI frames…</div>}

      {link && (
        <>
          <div>
            <div className="label mb-1">Amplitude — subcarrier {sc} ({source})</div>
            <Sparkline values={amplitudeSeries} color="#4fd1e8" />
          </div>
          <div>
            <div className="label mb-1">Phase — subcarrier {sc} (unwrapped, radians)</div>
            <Sparkline values={phaseSeries} color="#ffb454" />
          </div>

          {latest?.features && (
            <div className="grid grid-cols-2 gap-3 border-t border-hairline pt-3 sm:grid-cols-4">
              <Stat label="Energy" value={latest.features.energy.toFixed(4)} />
              <Stat label="Amp. variance" value={latest.features.amplitude_variance.toFixed(4)} />
              <Stat label="Phase variance" value={latest.features.phase_variance.toFixed(4)} />
              <Stat label="Activity score" value={(latest.activity_score ?? 0).toFixed(3)} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="value-mono text-sm">{value}</div>
    </div>
  );
}
