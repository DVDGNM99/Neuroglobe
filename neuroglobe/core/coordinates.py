"""Shared Allen CCF coordinate conventions.

Neuroglobe uses physical axes in AP, DV, ML order, expressed in micrometres.
Allen experiment coordinates therefore map as x=AP, y=DV, z=ML.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


class PhysicalAxis(IntEnum):
    AP = 0
    DV = 1
    ML = 2


class Hemisphere(IntEnum):
    LEFT = 1
    RIGHT = 2
    BOTH = 3


@dataclass(frozen=True)
class AtlasGeometry:
    """Minimal physical geometry needed for axis-safe operations."""

    shape: tuple[int, int, int]
    spacing_um: tuple[float, float, float]
    origin_um: tuple[float, float, float] = (0.0, 0.0, 0.0)
    direction: tuple[float, ...] = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )

    def __post_init__(self) -> None:
        if len(self.shape) != 3 or any(value <= 0 for value in self.shape):
            raise ValueError("Atlas shape must contain three positive dimensions.")
        if len(self.spacing_um) != 3 or any(value <= 0 for value in self.spacing_um):
            raise ValueError("Atlas spacing must contain three positive values.")
        if len(self.origin_um) != 3:
            raise ValueError("Atlas origin must contain three values.")
        if len(self.direction) != 9:
            raise ValueError("Atlas direction must contain a flattened 3x3 matrix.")

    @classmethod
    def from_values(
        cls,
        shape: Iterable[int],
        spacing_um: Iterable[float],
        origin_um: Iterable[float] = (0.0, 0.0, 0.0),
        direction: Iterable[float] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    ) -> "AtlasGeometry":
        return cls(
            tuple(int(v) for v in shape),
            tuple(float(v) for v in spacing_um),
            tuple(float(v) for v in origin_um),
            tuple(float(v) for v in direction),
        )

    def midpoint_um(self, axis: PhysicalAxis) -> float:
        index = int(axis)
        return self.origin_um[index] + (
            self.shape[index] * self.spacing_um[index] / 2.0
        )

    @property
    def ml_midpoint_um(self) -> float:
        return self.midpoint_um(PhysicalAxis.ML)

    def index_to_physical(self, index: Iterable[float]) -> tuple[float, float, float]:
        """Transform an AP/DV/ML continuous index into physical micrometres."""

        values = tuple(float(value) for value in index)
        if len(values) != 3:
            raise ValueError("A spatial index must contain three values.")
        scaled = tuple(values[i] * self.spacing_um[i] for i in range(3))
        direction = tuple(self.direction[row * 3 : row * 3 + 3] for row in range(3))
        return tuple(
            self.origin_um[row]
            + sum(direction[row][column] * scaled[column] for column in range(3))
            for row in range(3)
        )


ALLEN_CCF_25UM = AtlasGeometry(
    shape=(528, 320, 456),
    spacing_um=(25.0, 25.0, 25.0),
)


def injection_hemisphere(
    injection_ml_um: float | int | None,
    *,
    midpoint_um: float = ALLEN_CCF_25UM.ml_midpoint_um,
) -> Hemisphere | None:
    """Classify an injection using Allen ``injection_z`` (the ML coordinate).

    A coordinate exactly on the midline, missing, or non-numeric is deliberately
    returned as unknown instead of silently assigning it to one hemisphere.
    """

    if injection_ml_um is None:
        return None
    try:
        coordinate = float(injection_ml_um)
    except (TypeError, ValueError):
        return None
    if coordinate < midpoint_um:
        return Hemisphere.LEFT
    if coordinate > midpoint_um:
        return Hemisphere.RIGHT
    return None


def lateralization(
    target_hemisphere_id: int | float | None,
    injection_side: Hemisphere | None,
) -> str:
    """Return Ipsilateral, Contralateral, Midline, or Unknown."""

    try:
        target = Hemisphere(int(target_hemisphere_id))
    except (TypeError, ValueError):
        return "Unknown"
    if target is Hemisphere.BOTH:
        return "Midline"
    if injection_side is None:
        return "Unknown"
    return "Ipsilateral" if target is injection_side else "Contralateral"
