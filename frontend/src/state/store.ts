import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import { connectStream } from "../api/ws";
import type { CSIPreview, LayerKey, MapSnapshot, TabKey } from "../types";

interface AppState {
  snapshot: MapSnapshot | null;
  connected: boolean;
  csiHistory: Record<string, CSIPreview[]>; // link_id -> recent frames (bounded)
  activeTab: TabKey;
  layers: Record<LayerKey, boolean>;
  zSlice: number; // meters
  viewMode: "orbit" | "top" | "first_person";
  selectedSensorId: string | null;

  setActiveTab: (t: TabKey) => void;
  toggleLayer: (k: LayerKey) => void;
  setZSlice: (z: number) => void;
  setViewMode: (v: "orbit" | "top" | "first_person") => void;
  setSelectedSensor: (id: string | null) => void;
  connect: () => void;
}

const MAX_CSI_HISTORY = 120;

// Module-level (not component-level) guard: `connect()` is called from
// App's top-level useEffect, which React 18 StrictMode intentionally
// double-invokes in development (mount -> cleanup -> mount again) to
// surface exactly this kind of bug. Without this guard, connect() would
// open a second, independent pair of WebSocket connections that's never
// closed, each pushing its own `set()` calls into the same store.
let socketsInitialized = false;

export const useAppStore = create<AppState>()(
  subscribeWithSelector((set, get) => ({
  snapshot: null,
  connected: false,
  csiHistory: {},
  activeTab: "map",
  layers: {
    sensors: true,
    environment: true,
    occupancy: true,
    movement: true,
    rf_field: false,
    confidence: true,
    historical_trails: false,
    pose_skeleton: false,
  },
  zSlice: 1.0,
  viewMode: "orbit",
  selectedSensorId: null,

  setActiveTab: (t) => set({ activeTab: t }),
  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
  setZSlice: (z) => set({ zSlice: z }),
  setViewMode: (v) => set({ viewMode: v }),
  setSelectedSensor: (id) => set({ selectedSensorId: id }),

  connect: () => {
    if (socketsInitialized) return;
    socketsInitialized = true;
    connectStream<MapSnapshot>(
      "/ws/map",
      (snapshot) => set({ snapshot }),
      (connected) => set({ connected })
    );
    connectStream<CSIPreview>("/ws/csi", (preview) => {
      if (!preview.valid) return;
      const history = { ...get().csiHistory };
      const arr = [...(history[preview.link_id] || []), preview];
      history[preview.link_id] = arr.slice(-MAX_CSI_HISTORY);
      set({ csiHistory: history });
    });
  },
}))
);
