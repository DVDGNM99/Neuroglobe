"""Dependency-light scientific validation helpers for spatial artifacts.

Arrays handled here follow the Neuroglobe AP/DV/ML convention.  Physical
distances are expressed in micrometres and include spacing, origin, and the
3x3 direction matrix stored in :class:`~neuroglobe.core.coordinates.AtlasGeometry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Mapping, Sequence

import numpy as np

from neuroglobe.core.coordinates import AtlasGeometry


Index3D = tuple[int, int, int]


@dataclass(frozen=True)
class AsymmetricPhantom:
    """Small, deliberately non-symmetric volume with named landmarks."""

    mask: np.ndarray
    geometry: AtlasGeometry
    landmarks: Mapping[str, Index3D]


@dataclass(frozen=True)
class SpatialValidationResult:
    """Metrics used to accept or reject a spatial transformation."""

    dice: float
    hausdorff_um: float
    centroid_error_um: float
    passed: bool


def make_asymmetric_phantom() -> AsymmetricPhantom:
    """Return a tiny AP/DV/ML fixture that exposes flips and permutations.

    The two components differ in size and occupy different octants.  Three
    named landmarks make header-only errors observable even when index-space
    arrays are identical.
    """

    geometry = AtlasGeometry.from_values(
        shape=(17, 13, 19),
        spacing_um=(25.0, 40.0, 60.0),
        origin_um=(100.0, -80.0, 250.0),
    )
    mask = np.zeros(geometry.shape, dtype=bool)
    mask[2:6, 2:5, 3:6] = True
    mask[10:15, 7:11, 12:18] = True
    mask[8, 3, 14] = True
    landmarks: dict[str, Index3D] = {
        "anterior_left": (2, 2, 3),
        "posterior_right": (14, 10, 17),
        "dorsal_bridge": (8, 3, 14),
    }
    return AsymmetricPhantom(mask=mask, geometry=geometry, landmarks=landmarks)


def dice_coefficient(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Compute the Sørensen-Dice coefficient for equal-shape binary masks."""

    reference_mask = np.asarray(reference, dtype=bool)
    candidate_mask = np.asarray(candidate, dtype=bool)
    if reference_mask.shape != candidate_mask.shape:
        raise ValueError(
            "Dice requires equal array shapes: "
            f"{reference_mask.shape} != {candidate_mask.shape}."
        )
    denominator = int(reference_mask.sum()) + int(candidate_mask.sum())
    if denominator == 0:
        return 1.0
    intersection = int(np.logical_and(reference_mask, candidate_mask).sum())
    return 2.0 * intersection / denominator


def physical_points(mask: np.ndarray, geometry: AtlasGeometry) -> np.ndarray:
    """Return physical AP/DV/ML coordinates for every non-zero voxel."""

    binary = np.asarray(mask, dtype=bool)
    if binary.shape != geometry.shape:
        raise ValueError(
            f"Mask shape {binary.shape} does not match geometry {geometry.shape}."
        )
    indices = np.argwhere(binary).astype(float)
    if not len(indices):
        return np.empty((0, 3), dtype=float)
    scaled = indices * np.asarray(geometry.spacing_um, dtype=float)
    direction = np.asarray(geometry.direction, dtype=float).reshape(3, 3)
    origin = np.asarray(geometry.origin_um, dtype=float)
    points = np.empty_like(scaled)
    for row in range(3):
        points[:, row] = origin[row]
        for column in range(3):
            points[:, row] += scaled[:, column] * direction[row, column]
    return points


def _nearest_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return exact nearest-neighbour distances with bounded temporary memory."""

    distances = np.full(len(source), inf, dtype=float)
    block_size = 512
    for start in range(0, len(source), block_size):
        block = source[start : start + block_size]
        squared = np.sum((block[:, None, :] - target[None, :, :]) ** 2, axis=2)
        distances[start : start + len(block)] = np.sqrt(np.min(squared, axis=1))
    return distances


def hausdorff_distance_um(
    reference: np.ndarray,
    candidate: np.ndarray,
    reference_geometry: AtlasGeometry,
    candidate_geometry: AtlasGeometry | None = None,
) -> float:
    """Compute symmetric physical-space Hausdorff distance in micrometres."""

    candidate_geometry = candidate_geometry or reference_geometry
    reference_points = physical_points(reference, reference_geometry)
    candidate_points = physical_points(candidate, candidate_geometry)
    if not len(reference_points) and not len(candidate_points):
        return 0.0
    if not len(reference_points) or not len(candidate_points):
        return inf
    return float(
        max(
            np.max(_nearest_distances(reference_points, candidate_points)),
            np.max(_nearest_distances(candidate_points, reference_points)),
        )
    )


def centroid_error_um(
    reference: np.ndarray,
    candidate: np.ndarray,
    reference_geometry: AtlasGeometry,
    candidate_geometry: AtlasGeometry | None = None,
) -> float:
    """Return the Euclidean distance between physical mask centroids."""

    candidate_geometry = candidate_geometry or reference_geometry
    reference_points = physical_points(reference, reference_geometry)
    candidate_points = physical_points(candidate, candidate_geometry)
    if not len(reference_points) and not len(candidate_points):
        return 0.0
    if not len(reference_points) or not len(candidate_points):
        return inf
    delta = reference_points.mean(axis=0) - candidate_points.mean(axis=0)
    return float(np.sqrt(np.sum(delta * delta)))


def landmark_errors_um(
    reference: Mapping[str, Sequence[int]],
    candidate: Mapping[str, Sequence[int]],
    reference_geometry: AtlasGeometry,
    candidate_geometry: AtlasGeometry | None = None,
) -> dict[str, float]:
    """Compare matching named landmarks in physical space."""

    candidate_geometry = candidate_geometry or reference_geometry
    missing = set(reference) ^ set(candidate)
    if missing:
        raise ValueError(f"Landmark sets differ: {sorted(missing)}")
    errors: dict[str, float] = {}
    for name, reference_index in reference.items():
        reference_point = reference_geometry.index_to_physical(reference_index)
        candidate_point = candidate_geometry.index_to_physical(candidate[name])
        delta = np.subtract(reference_point, candidate_point)
        errors[name] = float(np.sqrt(np.sum(delta * delta)))
    return errors


def validate_binary_alignment(
    reference: np.ndarray,
    candidate: np.ndarray,
    reference_geometry: AtlasGeometry,
    candidate_geometry: AtlasGeometry | None = None,
    *,
    minimum_dice: float = 0.99,
    maximum_hausdorff_um: float = 25.0,
    maximum_centroid_error_um: float = 25.0,
) -> SpatialValidationResult:
    """Evaluate index overlap and physical alignment against explicit limits."""

    candidate_geometry = candidate_geometry or reference_geometry
    dice = dice_coefficient(reference, candidate)
    hausdorff = hausdorff_distance_um(
        reference, candidate, reference_geometry, candidate_geometry
    )
    centroid_error = centroid_error_um(
        reference, candidate, reference_geometry, candidate_geometry
    )
    return SpatialValidationResult(
        dice=dice,
        hausdorff_um=hausdorff,
        centroid_error_um=centroid_error,
        passed=(
            dice >= minimum_dice
            and hausdorff <= maximum_hausdorff_um
            and centroid_error <= maximum_centroid_error_um
        ),
    )
