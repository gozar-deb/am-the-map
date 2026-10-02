from __future__ import annotations

from app.mapping.voxel_grid import VoxelGrid


def test_deposit_and_read():
    grid = VoxelGrid(bounds_m=(5, 5, 3), resolution_m=0.2)
    grid.deposit(center=(2.5, 2.5, 1.0), occupancy=0.8, movement=0.3, rf_intensity=0.5, confidence=0.6, radius_m=0.5)
    voxels = grid.as_sparse_list(threshold=0.01)
    assert len(voxels) > 0
    assert all(v["occupancy_probability"] <= 1.0 for v in voxels)


def test_decay_reduces_and_removes():
    grid = VoxelGrid(bounds_m=(5, 5, 3), resolution_m=0.2)
    grid.deposit(center=(1.0, 1.0, 1.0), occupancy=0.1, movement=0.0, rf_intensity=0.1, confidence=0.5, radius_m=0.3)
    before = len(grid.voxels)
    for _ in range(30):
        grid.decay(factor=0.5, floor=0.02)
    assert len(grid.voxels) <= before


def test_world_to_index_clips_to_bounds():
    grid = VoxelGrid(bounds_m=(5, 5, 3), resolution_m=0.5)
    i, j, k = grid.world_to_index(100, -100, 100)
    assert 0 <= i < grid.nx
    assert 0 <= j < grid.ny
    assert 0 <= k < grid.nz


def test_resolution_presets():
    from app.mapping.voxel_grid import VALID_RESOLUTIONS_M

    assert 0.05 in VALID_RESOLUTIONS_M
    assert 0.5 in VALID_RESOLUTIONS_M
