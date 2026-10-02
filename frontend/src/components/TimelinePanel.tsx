import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { SessionInfo } from "../types";

export default function TimelinePanel() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [recordingName, setRecordingName] = useState("session");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => api.sessions().then(setSessions).catch(() => {});

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  async function startRecording() {
    const session = await api.startRecording(recordingName || "session");
    setActiveSessionId(session.id);
    refresh();
  }

  async function stopRecording() {
    if (!activeSessionId) return;
    await api.stopRecording(activeSessionId);
    setActiveSessionId(null);
    refresh();
  }

  async function replay(id: string) {
    await api.replaySession(id, 1.0);
    setMessage(`Replaying session ${id}…`);
    setTimeout(() => setMessage(null), 3000);
  }

  async function runCalibration() {
    setCalibrating(true);
    setMessage(null);
    try {
      const result = await api.calibrate("dashboard-calibration", 8);
      if ((result as any).error) {
        setMessage((result as any).error as string);
      } else {
        setMessage(
          `Calibration confidence ${(result as any).calibration_confidence_pct}% — baseline saved.`
        );
      }
    } finally {
      setCalibrating(false);
    }
  }

  return (
    <div className="scanlines flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={recordingName}
          onChange={(e) => setRecordingName(e.target.value)}
          placeholder="session name"
          className="border border-hairline bg-panel2 px-2 py-1 font-mono text-xs text-ink"
        />
        {!activeSessionId ? (
          <button onClick={startRecording} className="border border-signal/50 px-3 py-1 font-mono text-xs text-signal hover:bg-signal/10">
            ● Record
          </button>
        ) : (
          <button onClick={stopRecording} className="border border-danger/50 px-3 py-1 font-mono text-xs text-danger hover:bg-danger/10">
            ■ Stop
          </button>
        )}
        <button
          onClick={runCalibration}
          disabled={calibrating}
          className="border border-hairline px-3 py-1 font-mono text-xs text-muted hover:text-ink disabled:opacity-50"
        >
          {calibrating ? "Calibrating…" : "Run calibration baseline"}
        </button>
        {message && <span className="text-xs text-muted">{message}</span>}
      </div>

      <div className="border border-hairline">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-hairline text-left text-muted">
              <th className="px-2 py-1.5 font-normal">Session</th>
              <th className="px-2 py-1.5 font-normal">Status</th>
              <th className="px-2 py-1.5 font-normal">Source</th>
              <th className="px-2 py-1.5 font-normal">Frames</th>
              <th className="px-2 py-1.5 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 && (
              <tr>
                <td colSpan={5} className="px-2 py-3 text-center text-muted">
                  No sessions recorded yet.
                </td>
              </tr>
            )}
            {sessions.map((s) => (
              <tr key={s.id} className="border-b border-hairline last:border-b-0">
                <td className="px-2 py-1.5 value-mono">{s.name}</td>
                <td className="px-2 py-1.5">{s.status}</td>
                <td className="px-2 py-1.5">{s.source}</td>
                <td className="px-2 py-1.5 value-mono">{s.frame_count}</td>
                <td className="px-2 py-1.5 text-right">
                  {s.status === "stopped" && (
                    <button onClick={() => replay(s.id)} className="text-signal hover:underline">
                      Replay
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-muted">
        Replaying a session reproduces the original visualization/inference timeline exactly (spec §30) by
        feeding recorded frames back through the same pipeline. Compare two sessions by replaying each and
        reading their reports (Export tab / <span className="value-mono">am-map export</span>).
      </div>
    </div>
  );
}
