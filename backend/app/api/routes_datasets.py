from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.datasets import service
from app.schemas import DatasetCreate, DatasetExport, DatasetImport

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("")
async def list_datasets():
    return service.list_datasets()


@router.post("")
async def create_dataset(payload: DatasetCreate):
    try:
        return service.create_dataset(payload.name, payload.description)
    except FileExistsError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/import")
async def import_dataset(payload: DatasetImport):
    try:
        return service.import_dataset(payload.name, payload.source_dir)
    except (FileExistsError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/export")
async def export_dataset(payload: DatasetExport):
    try:
        path = service.export_dataset(payload.name, payload.dest_dir)
        return {"archive_path": path}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{name}")
async def inspect_dataset(name: str):
    try:
        return service.inspect_dataset(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
