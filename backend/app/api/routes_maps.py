from __future__ import annotations

from fastapi import APIRouter

from app.core.runtime import engine
from app.mapping.voxel_grid import VALID_RESOLUTIONS_M
from app.schemas import VoxelConfigUpdate

router = APIRouter(prefix="/api/maps", tags=["maps"])


@router.get("/current")
async def current_map():
    """The live probabilistic RF spatial map (section 8): occupancy,
    movement, confidence, RF intensity per voxel, plus sensors and tracked
    objects. Always includes a `provenance` field -- see section 55."""
    return engine.last_snapshot or {"note": "No data yet -- start the pipeline (POST /api/system/start)."}


@router.get("/config")
async def get_map_config():
    return {
        "resolution_m": engine.grid.resolution_m,
        "bounds_m": list(engine.grid.bounds_m),
        "valid_resolution_presets_m": list(VALID_RESOLUTIONS_M),
        "grid_dims": [engine.grid.nx, engine.grid.ny, engine.grid.nz],
    }


@router.put("/config")
async def update_map_config(payload: VoxelConfigUpdate):
    """Changing resolution rebuilds the grid (section 8: resolution is
    configurable, and higher isn't automatically better -- coarser grids
    are cheaper and more stable on low-end hardware)."""
    bounds = payload.bounds_m or engine.grid.bounds_m
    engine.grid.resize(bounds, payload.resolution_m)
    return await get_map_config()
