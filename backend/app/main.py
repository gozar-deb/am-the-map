from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_ai,
    routes_calibration,
    routes_datasets,
    routes_experiments,
    routes_maps,
    routes_models,
    routes_occupancy,
    routes_reports,
    routes_sensors,
    routes_sessions,
    routes_system,
    routes_tracking,
    websockets,
)
from app.core import runtime
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.database.db import init_db

configure_logging()
logger = get_logger("main")

# Paths that stay open even when API_TOKEN is set
_OPEN_PATHS = frozenset({"/", "/api/status", "/api/system/doctor"})
_OPEN_PREFIXES = ("/docs", "/redoc", "/openapi.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "startup",
        app=settings.app_name,
        ai_mode=settings.ai_mode.value,
        privacy_mode=settings.privacy_mode,
    )
    if settings.simulator_enabled:
        await runtime.start_pipeline(mode="simulated")
        logger.info("simulator.autostarted")
    yield
    await runtime.stop_pipeline()
    logger.info("shutdown")


app = FastAPI(title=settings.app_name, version="0.2.4", lifespan=lifespan)


@app.middleware("http")
async def optional_auth_middleware(request, call_next):
    """When API_TOKEN is set, require Bearer / X-API-Token on protected routes.

    Always allows CORS preflight (OPTIONS) so browsers can negotiate headers.
    """
    from app.core.auth import auth_enabled, _token_ok

    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if auth_enabled():
        is_open = path in _OPEN_PATHS or any(
            path == p or path.startswith(p + "/") for p in _OPEN_PREFIXES
        )
        if not is_open:
            auth = request.headers.get("authorization")
            bearer = (
                auth[7:].strip()
                if auth and auth.lower().startswith("bearer ")
                else None
            )
            token = request.headers.get("x-api-token") or bearer
            if not _token_ok(token):
                return JSONResponse(
                    {"detail": "Invalid or missing API token"}, status_code=401
                )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router_module in (
    routes_system,
    routes_sensors,
    routes_sessions,
    routes_maps,
    routes_occupancy,
    routes_tracking,
    routes_calibration,
    routes_models,
    routes_experiments,
    routes_ai,
    routes_reports,
    routes_datasets,
    websockets,
):
    app.include_router(router_module.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "tagline": "An experimental RF spatial perception platform that transforms "
        "wireless measurements into probabilistic 3D representations of environments.",
        "version": "0.2.4",
        "docs": "/docs",
    }
