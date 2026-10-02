import { useEffect, useRef } from "react";
import { useAppStore } from "../state/store";

const Z_PRESETS = [0.2, 0.5, 1.0, 1.5, 2.0];

export default function HeatmapPanel() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const snapshot = useAppStore((s) => s.snapshot);
  const zSlice = useAppStore((s) => s.zSlice);
  const setZSlice = useAppStore((s) => s.setZSlice);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !snapshot) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#0a0e13";
    ctx.fillRect(0, 0, w, h);

    const [bx, by] = snapshot.environment.bounds_m;
    const tolerance = snapshot.environment.voxel_resolution_m;

    for (const v of snapshot.voxels) {
      const [wx, wy, wz] = v.world;
      if (Math.abs(wz - zSlice) > tolerance) continue;
      const px = (wx / bx) * w;
      const py = h - (wy / by) * h;
      const intensity = Math.max(v.rf_intensity, v.occupancy_probability * 0.7);
      if (intensity < 0.03) continue;
      const radius = 14 + intensity * 22;
      const grad = ctx.createRadialGradient(px, py, 0, px, py, radius);
      grad.addColorStop(0, `rgba(79, 209, 232, ${Math.min(0.9, intensity)})`);
      grad.addColorStop(0.6, `rgba(255, 180, 84, ${Math.min(0.4, intensity * 0.5)})`);
      grad.addColorStop(1, "rgba(79, 209, 232, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.fill();
    }

    // sensors overlay
    for (const s of snapshot.sensors) {
      const px = (s.position[0] / bx) * w;
      const py = h - (s.position[1] / by) * h;
      ctx.fillStyle = s.status === "online" ? "#4fd1e8" : "#3e4a55";
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#6b7a87";
      ctx.font = "10px 'IBM Plex Mono', monospace";
      ctx.fillText(s.id, px + 6, py - 6);
    }
  }, [snapshot, zSlice]);

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <span className="label">Z-plane</span>
        <input
          type="range"
          min={0.1}
          max={2.5}
          step={0.05}
          value={zSlice}
          onChange={(e) => setZSlice(parseFloat(e.target.value))}
          className="w-48 accent-signal"
        />
        <span className="value-mono text-signal">{zSlice.toFixed(2)} m</span>
        <div className="flex gap-2">
          {Z_PRESETS.map((z) => (
            <button key={z} onClick={() => setZSlice(z)} className="font-mono text-[11px] text-muted hover:text-signal">
              {z}m
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 border border-hairline">
        <canvas ref={canvasRef} width={640} height={480} className="h-full w-full" />
      </div>
    </div>
  );
}
