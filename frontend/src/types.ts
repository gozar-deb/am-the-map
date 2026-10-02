export type Provenance = "real_sensor_data" | "simulated_data" | "replayed_data" | "none";

export interface SensorInfo {
  id: string;
  name?: string;
  hardware_type?: string;
  status: "online" | "offline" | "degraded";
  position: [number, number, number];
  csi_hz: number | null;
  packet_loss_pct?: number;
  latency_ms?: number;
  persisted?: boolean;
}

export interface TrackedObjectInfo {
  id: string;
  x: number;
  y: number;
  z: number;
  velocity_mps: number;
  confidence: number;
  trail: [number, number][];
  source: string;
}

export interface VoxelInfo {
  x: number;
  y: number;
  z: number;
  world: [number, number, number];
  occupancy_probability: number;
  movement_probability: number;
  rf_intensity: number;
  confidence: number;
  timestamp: number;
}

export interface EnvironmentInfo {
  bounds_m: [number, number, number];
  voxel_resolution_m: number;
  occupancy_count_estimate: number;
  occupancy_probability: number;
  movement_probability: number;
  confidence: number;
  avg_csi_hz: number;
  change_state: string;
  model: string;
  model_is_baseline: boolean;
  model_validated: boolean;
}

export interface MapSnapshot {
  timestamp: number;
  provenance: Provenance;
  sensors: SensorInfo[];
  environment: EnvironmentInfo;
  objects: TrackedObjectInfo[];
  voxels: VoxelInfo[];
  frame_count: number;
  rejected_count: number;
}

export interface CSIPreview {
  sensor_id: string;
  link_id: string;
  timestamp: number;
  valid: boolean;
  provenance?: Provenance;
  amplitude?: number[];
  phase?: number[];
  raw_amplitude?: number[];
  features?: {
    energy: number;
    amplitude_variance: number;
    phase_variance: number;
    temporal_delta: number;
  };
  activity_score?: number;
  reject_reason?: string;
}

export interface StatusResponse {
  app: string;
  environment: string;
  acquisition_mode: string;
  acquisition_running: boolean;
  recording: boolean;
  ai_mode: string;
  privacy_mode: boolean;
  map: MapSnapshot | { note: string };
}

export interface SessionInfo {
  id: string;
  name: string;
  status: string;
  source: string;
  started_at: string | null;
  ended_at: string | null;
  frame_count: number;
  recording_path: string | null;
}

export interface FindingInfo {
  id: string;
  kind: string;
  description: string;
  confidence: number;
  created_at: string;
}

export type LayerKey =
  | "sensors"
  | "environment"
  | "occupancy"
  | "movement"
  | "rf_field"
  | "confidence"
  | "historical_trails"
  | "pose_skeleton";

export type TabKey = "signal" | "map" | "occupancy" | "tracking" | "heatmap" | "timeline";
