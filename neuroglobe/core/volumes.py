"""Bounded-memory operations for large AP/DV/ML volumes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


DEFAULT_WORKING_MEMORY_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ChunkPlan:
    shape: tuple[int, ...]
    chunk_depth: int
    chunk_count: int
    working_memory_bytes: int


def plan_axis0_chunks(
    shape: tuple[int, ...],
    value_dtype: np.dtype | type,
    mask_dtype: np.dtype | type = np.bool_,
    *,
    maximum_working_bytes: int = DEFAULT_WORKING_MEMORY_BYTES,
) -> ChunkPlan:
    """Plan contiguous axis-0 chunks within a predictable working budget."""

    if not shape or any(int(dimension) <= 0 for dimension in shape):
        raise ValueError("Volume shape must contain positive dimensions.")
    if maximum_working_bytes <= 0:
        raise ValueError("maximum_working_bytes must be positive.")
    plane_voxels = int(np.prod(shape[1:], dtype=np.int64)) if len(shape) > 1 else 1
    bytes_per_plane = plane_voxels * (
        np.dtype(value_dtype).itemsize + np.dtype(mask_dtype).itemsize
    )
    chunk_depth = max(1, min(int(shape[0]), maximum_working_bytes // bytes_per_plane))
    chunk_count = (int(shape[0]) + chunk_depth - 1) // chunk_depth
    return ChunkPlan(
        shape=tuple(int(value) for value in shape),
        chunk_depth=chunk_depth,
        chunk_count=chunk_count,
        working_memory_bytes=chunk_depth * bytes_per_plane,
    )


def iter_axis0_chunks(plan: ChunkPlan) -> Iterator[tuple[slice, ...]]:
    """Yield n-dimensional slice tuples described by ``plan``."""

    tail = (slice(None),) * (len(plan.shape) - 1)
    for start in range(0, plan.shape[0], plan.chunk_depth):
        stop = min(start + plan.chunk_depth, plan.shape[0])
        yield (slice(start, stop), *tail)


def apply_binary_mask_inplace(
    values: np.ndarray,
    mask: np.ndarray,
    *,
    maximum_working_bytes: int = DEFAULT_WORKING_MEMORY_BYTES,
) -> ChunkPlan:
    """Mask an ndarray or memmap in place without allocating a full-size copy."""

    if values.shape != mask.shape:
        raise ValueError(f"Volume/mask shape mismatch: {values.shape} != {mask.shape}.")
    if not values.flags.writeable:
        raise ValueError("Volume must be writeable for in-place masking.")
    plan = plan_axis0_chunks(
        values.shape,
        values.dtype,
        mask.dtype,
        maximum_working_bytes=maximum_working_bytes,
    )
    for chunk in iter_axis0_chunks(plan):
        np.multiply(values[chunk], mask[chunk], out=values[chunk], casting="unsafe")
    return plan


def write_masked_npy(
    values: np.ndarray,
    mask: np.ndarray,
    destination: Path,
    *,
    maximum_working_bytes: int = DEFAULT_WORKING_MEMORY_BYTES,
) -> tuple[Path, ChunkPlan]:
    """Write a masked `.npy` array incrementally for out-of-core downstream use."""

    if values.shape != mask.shape:
        raise ValueError(f"Volume/mask shape mismatch: {values.shape} != {mask.shape}.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    plan = plan_axis0_chunks(
        values.shape,
        values.dtype,
        mask.dtype,
        maximum_working_bytes=maximum_working_bytes,
    )
    output = np.lib.format.open_memmap(
        destination,
        mode="w+",
        dtype=values.dtype,
        shape=values.shape,
    )
    try:
        for chunk in iter_axis0_chunks(plan):
            np.multiply(values[chunk], mask[chunk], out=output[chunk], casting="unsafe")
        output.flush()
    finally:
        del output
    return destination, plan
