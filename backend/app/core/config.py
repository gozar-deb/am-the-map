"""
Core configuration for Am the Map.

Reads everything from environment variables (see .env.example). Nothing is
ever hard-coded, and no API key is required for the core sensing/ML/mapping
pipeline to run -- see AI_MODE below.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIMode(str, Enum):
    """Operating modes for the optional generative-AI layer (section 19)."""

    LOCAL = "local"       # local models only (Ollama / LM Studio / custom endpoint)
    HYBRID = "hybrid"     # local RF/ML pipeline + optional cloud generative AI
    CLOUD = "cloud"       # cloud provider used where configured
    OFFLINE = "offline"   # all external network AI calls disabled (default)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "Am the Map"
    environment: str = Field(default="development")
    data_dir: Path = Field(default=Path("data"))
    database_url: str = Field(default="sqlite:///./data/am_the_map.db")

    # --- Sensing / acquisition ---
    default_sampling_hz: float = Field(default=20.0)
    simulator_enabled: bool = Field(default=True)

    # --- Voxel mapping (section 8) ---
    voxel_resolution_m: float = Field(default=0.20)  # 5/10/20/50 cm are the documented presets
    room_bounds_m: tuple[float, float, float] = Field(default=(5.0, 5.0, 3.0))

    # --- AI Gateway / privacy (sections 18-21) ---
    ai_mode: AIMode = Field(default=AIMode.OFFLINE)
    privacy_mode: bool = Field(default=True)  # when True: no external AI calls, no telemetry

    ai_default_provider: str = Field(default="none")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    xai_api_key: Optional[str] = Field(default=None, alias="XAI_API_KEY")
    kimi_api_key: Optional[str] = Field(default=None, alias="KIMI_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    nvidia_api_key: Optional[str] = Field(default=None, alias="NVIDIA_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, alias="MISTRAL_API_KEY")
    ollama_base_url: Optional[str] = Field(default="http://localhost:11434")
    lmstudio_base_url: Optional[str] = Field(default="http://localhost:1234/v1")
    custom_local_endpoint: Optional[str] = Field(default=None)

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    # Optional shared secret. Empty = open (local research default).
    api_token: Optional[str] = Field(default=None, alias="API_TOKEN")
    # Simple AI rate limit (requests per minute per process)
    ai_rate_limit_per_minute: int = Field(default=30)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    def any_cloud_key_configured(self) -> bool:
        return any(
            [
                self.openai_api_key,
                self.anthropic_api_key,
                self.xai_api_key,
                self.kimi_api_key,
                self.gemini_api_key,
                self.deepseek_api_key,
                self.nvidia_api_key,
                self.openrouter_api_key,
                self.groq_api_key,
                self.mistral_api_key,
            ]
        )

    def external_ai_allowed(self) -> bool:
        """Single source of truth for whether an outbound AI network call may occur."""
        if self.privacy_mode:
            return False
        if self.ai_mode == AIMode.OFFLINE:
            return False
        return True


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "recordings").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "models").mkdir(parents=True, exist_ok=True)
