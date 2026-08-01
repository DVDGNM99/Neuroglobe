"""Physical geometry inspection for integrated NRRD scenes."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from neuroglobe.core.coordinates import AtlasGeometry


_HEADER_LIMIT_BYTES = 1024 * 1024
_VECTOR_PATTERN = re.compile(r"\([^)]*\)|none", re.IGNORECASE)


@dataclass(frozen=True)
class VolumeGeometry:
    """Spatial frame plus AP/DV/ML voxel geometry from an NRRD header."""

    geometry: AtlasGeometry
    space: str

    def __post_init__(self) -> None:
        if not self.space.strip():
            raise ValueError("NRRD space must not be empty.")

    def to_dict(self) -> dict[str, object]:
        return {
            "space": self.space,
            "shape": list(self.geometry.shape),
            "spacing_um": list(self.geometry.spacing_um),
            "origin_um": list(self.geometry.origin_um),
            "direction": list(self.geometry.direction),
        }

    @classmethod
    def from_dict(cls, value: object) -> "VolumeGeometry":
        if not isinstance(value, dict):
            raise ValueError("Layer geometry must be an object.")
        try:
            geometry = AtlasGeometry.from_values(
                value["shape"],
                value["spacing_um"],
                value.get("origin_um", (0.0, 0.0, 0.0)),
                value.get(
                    "direction",
                    (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
                ),
            )
            space = str(value["space"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid layer geometry: {error}") from error
        return cls(geometry=geometry, space=space)


def _read_header(path: Path) -> str:
    data = bytearray()
    with Path(path).open("rb") as stream:
        while len(data) < _HEADER_LIMIT_BYTES:
            block = stream.read(min(4096, _HEADER_LIMIT_BYTES - len(data)))
            if not block:
                break
            data.extend(block)
            for separator in (b"\r\n\r\n", b"\n\n"):
                boundary = data.find(separator)
                if boundary >= 0:
                    return bytes(data[:boundary]).decode("ascii")
    raise ValueError(f"NRRD header terminator not found within {_HEADER_LIMIT_BYTES} bytes.")


def _header_fields(header: str) -> dict[str, str]:
    lines = header.splitlines()
    if not lines or not lines[0].startswith("NRRD"):
        raise ValueError("File does not start with an NRRD magic header.")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def _parse_vector(value: str, *, field: str) -> tuple[float, float, float]:
    if not value.startswith("(") or not value.endswith(")"):
        raise ValueError(f"{field} must be a three-dimensional vector.")
    try:
        values = tuple(float(item.strip()) for item in value[1:-1].split(","))
    except ValueError as error:
        raise ValueError(f"{field} contains a non-numeric value.") from error
    if len(values) != 3 or not all(math.isfinite(item) for item in values):
        raise ValueError(f"{field} must contain three finite values.")
    return values


def read_nrrd_geometry(path: Path) -> VolumeGeometry:
    """Read spatial geometry without loading a potentially multi-GB payload."""

    path = Path(path)
    if path.suffix.lower() != ".nrrd":
        raise ValueError(f"Integrated volume layers require .nrrd files: {path.name}")
    fields = _header_fields(_read_header(path))
    if fields.get("dimension") != "3":
        raise ValueError("Integrated volume layers must be three-dimensional.")
    try:
        shape = tuple(int(item) for item in fields["sizes"].split())
        direction_tokens = _VECTOR_PATTERN.findall(fields["space directions"])
        origin = _parse_vector(fields["space origin"], field="space origin")
        space = fields["space"]
    except KeyError as error:
        raise ValueError(f"NRRD spatial field is missing: {error.args[0]}") from error
    if len(shape) != 3 or any(item <= 0 for item in shape):
        raise ValueError("NRRD sizes must contain three positive integers.")
    if len(direction_tokens) != 3 or any(
        token.lower() == "none" for token in direction_tokens
    ):
        raise ValueError("NRRD must provide three spatial direction vectors.")

    vectors = tuple(
        _parse_vector(token, field="space directions") for token in direction_tokens
    )
    spacing = tuple(
        math.sqrt(sum(component * component for component in vector))
        for vector in vectors
    )
    if any(value <= 0 for value in spacing):
        raise ValueError("NRRD space directions must have non-zero length.")

    # NRRD lists one physical vector per data axis (matrix columns), while
    # AtlasGeometry stores a flattened row-major direction matrix.
    direction = tuple(
        vectors[column][row] / spacing[column]
        for row in range(3)
        for column in range(3)
    )
    return VolumeGeometry(
        geometry=AtlasGeometry.from_values(shape, spacing, origin, direction),
        space=space,
    )


def geometry_compatibility_errors(
    candidate: VolumeGeometry,
    reference: VolumeGeometry,
    *,
    tolerance_um: float = 1e-3,
    direction_tolerance: float = 1e-6,
) -> tuple[str, ...]:
    """Compare physical frames while allowing one voxel of edge rounding."""

    errors: list[str] = []
    if candidate.space.casefold() != reference.space.casefold():
        errors.append(f"space mismatch: {candidate.space!r} != {reference.space!r}")
    for index, (left, right) in enumerate(
        zip(candidate.geometry.origin_um, reference.geometry.origin_um)
    ):
        if abs(left - right) > tolerance_um:
            errors.append(f"origin[{index}] mismatch: {left} != {right}")
    for index, (left, right) in enumerate(
        zip(candidate.geometry.direction, reference.geometry.direction)
    ):
        if abs(left - right) > direction_tolerance:
            errors.append(f"direction[{index}] mismatch: {left} != {right}")

    candidate_extent = tuple(
        candidate.geometry.shape[index] * candidate.geometry.spacing_um[index]
        for index in range(3)
    )
    reference_extent = tuple(
        reference.geometry.shape[index] * reference.geometry.spacing_um[index]
        for index in range(3)
    )
    for index, (left, right) in enumerate(zip(candidate_extent, reference_extent)):
        one_voxel = max(
            candidate.geometry.spacing_um[index], reference.geometry.spacing_um[index]
        )
        if abs(left - right) > one_voxel + tolerance_um:
            errors.append(f"extent[{index}] mismatch: {left} != {right} um")
    return tuple(errors)


def geometry_identity_errors(
    candidate: VolumeGeometry,
    expected: VolumeGeometry,
) -> tuple[str, ...]:
    """Compare stored and current file geometry without resolution tolerance."""

    errors = list(geometry_compatibility_errors(candidate, expected))
    if candidate.geometry.shape != expected.geometry.shape:
        errors.append(
            f"shape mismatch: {candidate.geometry.shape} != {expected.geometry.shape}"
        )
    for field_name in ("spacing_um", "origin_um", "direction"):
        left = getattr(candidate.geometry, field_name)
        right = getattr(expected.geometry, field_name)
        if any(abs(a - b) > 1e-6 for a, b in zip(left, right)):
            message = f"{field_name} mismatch: {left} != {right}"
            if message not in errors:
                errors.append(message)
    return tuple(errors)
