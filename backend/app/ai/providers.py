"""
AI Gateway provider clients (section 18).

This is intentionally separate from the Spatial ML Engine (ml/). These
clients only ever see structured map summaries built by ai/context.py, never
raw CSI, unless a caller explicitly opts in (section 20). No key is ever
hard-coded -- everything comes from environment variables via
core/config.py, and a provider reports itself `available()==False` if its
key/endpoint isn't configured, rather than failing confusingly later.
"""
from __future__ import annotations

import abc

import httpx

from app.core.config import settings


class BaseProvider(abc.ABC):
    name: str
    default_model: str = ""

    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    async def chat(self, system: str, user: str, model: str | None = None, max_tokens: int = 800) -> str: ...


class OpenAICompatibleProvider(BaseProvider):
    """Covers OpenAI, xAI Grok, Moonshot Kimi, DeepSeek, Groq, Mistral,
    OpenRouter, NVIDIA NIM, Ollama, LM Studio, and any other
    OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, name: str, base_url: str, api_key: str | None, default_model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model

    def available(self) -> bool:
        # Local servers (Ollama/LM Studio) don't require a key.
        if self.name in ("ollama", "lmstudio", "custom_local"):
            return bool(self.base_url)
        return bool(self.api_key and self.base_url)

    async def chat(self, system: str, user: str, model: str | None = None, max_tokens: int = 800) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def chat(self, system: str, user: str, model: str | None = None, max_tokens: int = 800) -> str:
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return "".join(block.get("text", "") for block in data.get("content", []))


class GeminiProvider(BaseProvider):
    name = "gemini"
    default_model = "gemini-2.5-flash"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    async def chat(self, system: str, user: str, model: str | None = None, max_tokens: int = 800) -> str:
        mdl = model or self.default_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def build_provider_registry() -> dict[str, BaseProvider]:
    registry: dict[str, BaseProvider] = {
        "openai": OpenAICompatibleProvider("openai", "https://api.openai.com/v1", settings.openai_api_key, "gpt-4o-mini"),
        "xai": OpenAICompatibleProvider("xai", "https://api.x.ai/v1", settings.xai_api_key, "grok-2-latest"),
        "kimi": OpenAICompatibleProvider("kimi", "https://api.moonshot.ai/v1", settings.kimi_api_key, "moonshot-v1-8k"),
        "deepseek": OpenAICompatibleProvider("deepseek", "https://api.deepseek.com/v1", settings.deepseek_api_key, "deepseek-chat"),
        "groq": OpenAICompatibleProvider("groq", "https://api.groq.com/openai/v1", settings.groq_api_key, "llama-3.3-70b-versatile"),
        "mistral": OpenAICompatibleProvider("mistral", "https://api.mistral.ai/v1", settings.mistral_api_key, "mistral-large-latest"),
        "openrouter": OpenAICompatibleProvider("openrouter", "https://openrouter.ai/api/v1", settings.openrouter_api_key, "openrouter/auto"),
        "nvidia": OpenAICompatibleProvider("nvidia", "https://integrate.api.nvidia.com/v1", settings.nvidia_api_key, "meta/llama-3.1-70b-instruct"),
        "anthropic": AnthropicProvider(settings.anthropic_api_key),
        "gemini": GeminiProvider(settings.gemini_api_key),
        "ollama": OpenAICompatibleProvider("ollama", (settings.ollama_base_url or "") + "/v1", None, "llama3.1"),
        "lmstudio": OpenAICompatibleProvider("lmstudio", settings.lmstudio_base_url or "", None, "local-model"),
    }
    if settings.custom_local_endpoint:
        registry["custom_local"] = OpenAICompatibleProvider(
            "custom_local", settings.custom_local_endpoint, None, "local-model"
        )
    return registry
