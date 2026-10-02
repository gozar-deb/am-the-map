import type { FindingInfo, SessionInfo, StatusResponse } from "../types";

const BASE = import.meta.env.VITE_API_URL || "";
const API_TOKEN = (import.meta.env.VITE_API_TOKEN as string | undefined) || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (API_TOKEN) {
    headers["X-API-Token"] = API_TOKEN;
  }
  // Merge caller headers without wiping Content-Type / auth
  if (init?.headers) {
    const extra = init.headers;
    if (extra instanceof Headers) {
      extra.forEach((v, k) => {
        headers[k] = v;
      });
    } else if (Array.isArray(extra)) {
      for (const [k, v] of extra) headers[k] = v;
    } else {
      Object.assign(headers, extra as Record<string, string>);
    }
  }

  const { headers: _ignored, ...rest } = init || {};
  const resp = await fetch(`${BASE}${path}`, {
    ...rest,
    headers,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = JSON.stringify(await resp.json());
    } catch {
      /* ignore */
    }
    throw new Error(`${resp.status} ${path}: ${detail}`);
  }
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await resp.json()) as T;
  }
  return (await resp.text()) as unknown as T;
}

export const api = {
  status: () => request<StatusResponse>("/api/status"),
  doctor: () => request<Record<string, unknown>>("/api/system/doctor"),
  scan: () => request<Record<string, unknown>>("/api/system/scan"),
  startPipeline: (mode: string, recording_name?: string, extra?: Record<string, unknown>) =>
    request("/api/system/start", {
      method: "POST",
      body: JSON.stringify({ mode, recording_name, ...(extra || {}) }),
    }),
  stopPipeline: () => request("/api/system/stop", { method: "POST" }),

  sensors: () => request<Record<string, unknown>[]>("/api/sensors"),
  updateSensorPosition: (id: string, x: number, y: number, z: number) =>
    request(`/api/sensors/${id}/position`, {
      method: "PUT",
      body: JSON.stringify({ x, y, z }),
    }),

  sessions: () => request<SessionInfo[]>("/api/sessions"),
  startRecording: (name: string, source = "simulated") =>
    request<SessionInfo>("/api/sessions/record", {
      method: "POST",
      body: JSON.stringify({ name, source }),
    }),
  stopRecording: (id: string) =>
    request<SessionInfo>(`/api/sessions/${id}/stop`, { method: "POST" }),
  replaySession: (id: string, speed = 1.0) =>
    request(`/api/sessions/${id}/replay?speed=${speed}`, { method: "POST" }),

  calibrate: (name: string, duration_s: number) =>
    request<Record<string, unknown>>("/api/calibration/run", {
      method: "POST",
      body: JSON.stringify({ name, duration_s }),
    }),
  calibrationProfiles: () =>
    request<Record<string, unknown>[]>("/api/calibration/profiles"),

  occupancyHistory: (limit = 50) =>
    request<FindingInfo[]>(`/api/occupancy/history?limit=${limit}`),

  models: () => request<Record<string, unknown>[]>("/api/models"),

  aiStatus: () => request<Record<string, unknown>>("/api/ai/status"),
  aiAsk: (question: string, provider?: string) =>
    request<{
      answered: boolean;
      response?: string;
      provider?: string;
      message?: string;
    }>("/api/ai/ask", {
      method: "POST",
      body: JSON.stringify({ question, provider }),
    }),

  mapConfig: () => request<Record<string, unknown>>("/api/maps/config"),
  updateMapConfig: (resolution_m: number) =>
    request("/api/maps/config", {
      method: "PUT",
      body: JSON.stringify({ resolution_m }),
    }),

  report: (format: "markdown" | "json" | "html" = "json") =>
    request<Record<string, unknown> | string>("/api/reports", {
      method: "POST",
      body: JSON.stringify({ format }),
    }),
};
