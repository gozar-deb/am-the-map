"""
AI Gateway (sections 18-21).

This is explicitly NOT the spatial ML engine -- it's an optional layer that
can answer natural-language questions about a map that has already been
computed locally. `Settings.external_ai_allowed()` is the single choke point
that decides whether any network call may happen at all (Privacy Mode /
OFFLINE mode always win), so this is the only place in the codebase that is
allowed to make an outbound AI request.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.context import build_context
from app.ai.providers import build_provider_registry
from app.core.config import AIMode, settings
from app.core.logging import get_logger
from app.database.models import AIRequest

logger = get_logger("ai.gateway")

# Providers that talk to a network endpoint the person controls themselves
# (a local Ollama/LM Studio server, or a custom local endpoint) rather than
# a third-party cloud API.
LOCAL_PROVIDER_NAMES = {"ollama", "lmstudio", "custom_local"}


class AIGateway:
    def __init__(self) -> None:
        self._providers = build_provider_registry()

    def _candidate_providers(self) -> dict:
        """Respects AI_MODE (section 19): LOCAL must never silently fall
        back to a cloud provider just because a stray API key happens to be
        set in the environment."""
        if settings.ai_mode == AIMode.LOCAL:
            return {k: v for k, v in self._providers.items() if k in LOCAL_PROVIDER_NAMES}
        return self._providers

    def status(self) -> dict:
        candidates = self._candidate_providers()
        return {
            "ai_mode": settings.ai_mode.value,
            "privacy_mode": settings.privacy_mode,
            "external_ai_allowed": settings.external_ai_allowed(),
            "configured_providers": [name for name, p in candidates.items() if p.available()],
            "note": "Local providers (ollama/lmstudio) are listed if a base URL is set, "
            "even if no local server is actually reachable yet -- 'configured' does not mean 'verified'. "
            "When AI_MODE=local, only local providers are ever considered, regardless of which cloud "
            "API keys are set in the environment.",
        }

    def _resolve_provider(self, provider_name: str | None):
        candidates = self._candidate_providers()
        name = provider_name or settings.ai_default_provider
        if name and name != "none" and name in candidates:
            return candidates[name]
        # fall back to the first available configured provider *within the
        # allowed candidate set* -- e.g. in LOCAL mode this never falls
        # through to a cloud provider even if one is configured.
        for p in candidates.values():
            if p.available():
                return p
        return None

    async def ask(
        self,
        db: Session,
        question: str,
        snapshot: dict,
        provider_name: str | None = None,
        include_raw_features: bool = False,
        raw_features: dict | None = None,
    ) -> dict:
        if not settings.external_ai_allowed():
            reason = "privacy_mode" if settings.privacy_mode else "offline_mode"
            db.add(
                AIRequest(
                    provider="none",
                    mode=settings.ai_mode.value,
                    question=question,
                    context_summary=None,
                    response=None,
                    external_call_made=False,
                )
            )
            db.commit()
            return {
                "answered": False,
                "reason": reason,
                "message": (
                    "🔒 Privacy Mode / OFFLINE mode is enabled -- no external AI "
                    "request was made. Disable Privacy Mode and set AI_MODE to "
                    "hybrid or cloud to enable this feature."
                ),
            }

        provider = self._resolve_provider(provider_name)
        if provider is None:
            candidates = self._candidate_providers()
            if provider_name and provider_name not in candidates:
                return {
                    "answered": False,
                    "reason": "provider_not_allowed_in_mode",
                    "message": (
                        f"Provider '{provider_name}' isn't available in AI_MODE={settings.ai_mode.value}. "
                        + ("Only local providers (ollama/lmstudio/custom_local) are allowed in 'local' mode."
                           if settings.ai_mode == AIMode.LOCAL else "")
                    ),
                }
            return {
                "answered": False,
                "reason": "no_provider_configured",
                "message": "No AI provider is configured. Set an API key (see .env.example) or run a local server (Ollama/LM Studio) and set AI_DEFAULT_PROVIDER.",
            }

        context = build_context(snapshot, include_raw_features=include_raw_features, raw_features=raw_features)
        system_prompt = (
            "You are analyzing a probabilistic RF spatial map from WiFi CSI "
            "sensing. Only use the structured data provided. State confidence "
            "levels explicitly. Never claim camera-like or LiDAR-like certainty."
        )

        try:
            answer = await provider.chat(system_prompt, f"{context}\n\nQuestion: {question}")
        except Exception as exc:  # noqa: BLE001
            logger.info("ai.provider_error", provider=provider.name, error=str(exc))
            return {"answered": False, "reason": "provider_error", "message": str(exc)}

        db.add(
            AIRequest(
                provider=provider.name,
                mode=settings.ai_mode.value,
                question=question,
                context_summary=context[:2000],
                response=answer[:4000],
                external_call_made=True,
            )
        )
        db.commit()

        return {"answered": True, "provider": provider.name, "response": answer}


ai_gateway = AIGateway()
