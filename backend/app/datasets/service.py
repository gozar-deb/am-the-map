"""Dataset management (section 28). Filesystem-backed so datasets stay
portable and reproducible -- each dataset is a directory of the documented
shape plus a metadata.json manifest."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from app.core.config import settings
from app.core.util import safe_resolve_dir, sanitize_id

SUBDIRS = ("csi", "sensor_metadata", "calibration", "ground_truth", "labels", "predictions")


def _root() -> Path:
    root = settings.data_dir / "datasets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def dataset_path(name: str) -> Path:
    safe_name = sanitize_id(name, "dataset name")
    return _root() / safe_name


def create_dataset(name: str, description: str = "") -> dict:
    path = dataset_path(name)
    if path.exists():
        raise FileExistsError(f"Dataset '{name}' already exists at {path}")
    for sub in SUBDIRS:
        (path / sub).mkdir(parents=True, exist_ok=True)
    metadata = {
        "name": name,
        "description": description,
        "created_at": time.time(),
        "schema_version": 1,
    }
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def import_dataset(name: str, source_dir: str) -> dict:
    src = safe_resolve_dir(source_dir, "source_dir")
    if not src.exists():
        raise FileNotFoundError(str(src))
    if not src.is_dir():
        raise ValueError(f"source_dir must be a directory: {src}")
    dst = dataset_path(name)
    if dst.exists():
        raise FileExistsError(f"Dataset '{name}' already exists at {dst}")
    shutil.copytree(src, dst)
    for sub in SUBDIRS:
        (dst / sub).mkdir(parents=True, exist_ok=True)
    meta_file = dst / "metadata.json"
    if not meta_file.exists():
        meta_file.write_text(
            json.dumps(
                {"name": name, "imported_from": str(src), "created_at": time.time()},
                indent=2,
            )
        )
    return inspect_dataset(name)


def export_dataset(name: str, dest_dir: str) -> str:
    src = dataset_path(name)
    if not src.exists():
        raise FileNotFoundError(f"No dataset named '{name}'")
    dest_dir_path = safe_resolve_dir(dest_dir, "dest_dir")
    dest_dir_path.mkdir(parents=True, exist_ok=True)
    # Ensure archive lands inside the resolved dest dir only
    archive_base = dest_dir_path / sanitize_id(name, "dataset name")
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=src)
    return archive_path


def inspect_dataset(name: str) -> dict:
    path = dataset_path(name)
    if not path.exists():
        raise FileNotFoundError(f"No dataset named '{name}'")
    metadata = {}
    meta_file = path / "metadata.json"
    if meta_file.exists():
        metadata = json.loads(meta_file.read_text())
    counts = {}
    for sub in SUBDIRS:
        subdir = path / sub
        counts[sub] = len(list(subdir.glob("*"))) if subdir.exists() else 0
    return {"name": name, "path": str(path), "metadata": metadata, "file_counts": counts}


def list_datasets() -> list[dict]:
    root = _root()
    results = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        try:
            results.append(inspect_dataset(p.name))
        except ValueError:
            continue
    return results
