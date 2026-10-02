from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SensorPositionUpdate(BaseModel):
    x: float
    y: float
    z: float
    orientation_deg: float = 0.0


class SensorCreate(BaseModel):
    name: str
    hardware_type: str = "simulated"
    x: float = 0.0
    y: float = 0.0
    z: float = 2.0
    sampling_hz: float = 20.0
    channel: int = 6
    bandwidth_mhz: int = 20


class PipelineStartRequest(BaseModel):
    mode: str = Field(
        default="simulated",
        description="simulated | esp32 | linux_csi | file_replay",
    )
    recording_name: Optional[str] = None
    replay_session_id: Optional[str] = None
    replay_speed: float = 1.0
    # Live hardware connection (esp32 / linux_csi)
    port: Optional[str] = Field(default=None, description="Serial port e.g. /dev/ttyUSB0 or COM3")
    baud: int = Field(default=921600, description="Serial baud rate")
    udp_host: Optional[str] = Field(default=None, description="UDP bind/connect host")
    udp_port: Optional[int] = Field(default=None, description="UDP port for CSI datagrams")
    tcp_host: Optional[str] = Field(default=None, description="TCP CSI publisher host")
    tcp_port: Optional[int] = Field(default=None, description="TCP CSI publisher port")
    source_path: Optional[str] = Field(default=None, description="Named pipe or CSI log file path")
    sensor_id: Optional[str] = Field(default=None, description="Fallback sensor id")
    interface: Optional[str] = Field(default=None, description="WiFi interface name (linux_csi)")


class SessionCreate(BaseModel):
    name: str
    source: str = "simulated"


class CalibrationRequest(BaseModel):
    name: str = "calibration"
    duration_s: float = 10.0


class ExperimentCreate(BaseModel):
    name: str
    hardware: Optional[str] = None
    environment_desc: Optional[str] = None
    sampling_hz: float = 20.0
    model_name: Optional[str] = None
    duration_minutes: Optional[float] = None
    session_id: Optional[str] = None
    notes: Optional[str] = None


class DatasetCreate(BaseModel):
    name: str
    description: str = ""


class DatasetImport(BaseModel):
    name: str
    source_dir: str


class DatasetExport(BaseModel):
    name: str
    dest_dir: str


class AIAskRequest(BaseModel):
    question: str
    provider: Optional[str] = None
    include_raw_features: bool = False


class VoxelConfigUpdate(BaseModel):
    resolution_m: float
    bounds_m: Optional[tuple[float, float, float]] = None


class ReportRequest(BaseModel):
    session_id: Optional[str] = None
    experiment_id: Optional[str] = None
    format: str = Field(default="markdown", description="markdown | json | html")
