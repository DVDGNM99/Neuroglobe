"""Stream average-volume statistics to physically registered raw NRRD."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

import numpy as np

from neuroglobe.core.provenance import (
    COORDINATE_CONVENTION,
    RUN_SCHEMA,
    artifact_manifest,
    file_sha256,
    verify_manifest_integrity,
    write_json_immutable,
)
from neuroglobe.integration.geometry import VolumeGeometry


AVERAGE_STATISTICS = ("mean", "variance", "ci95_low", "ci95_high")


@dataclass(frozen=True)
class AverageNrrdExport:
    statistic: str
    nrrd_path: Path
    manifest_path: Path
    source_array_path: Path


def export_average_nrrd(
    run_manifest_path: Path,
    *,
    statistic: str,
    output_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> AverageNrrdExport:
    """Export one verified average statistic without loading it in full."""

    if statistic not in AVERAGE_STATISTICS:
        raise ValueError(
            f"Unknown average statistic {statistic!r}; choose {AVERAGE_STATISTICS}."
        )
    run_manifest_path = Path(run_manifest_path).resolve()
    manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    source_path, source_record, geometry = _validated_average_source(
        manifest,
        manifest_path=run_manifest_path,
        statistic=statistic,
    )

    output_path = Path(output_path).resolve()
    if output_path.suffix.lower() != ".nrrd":
        raise ValueError("Average-volume export path must end in .nrrd.")
    sidecar_path = output_path.with_suffix(".manifest.json")
    for candidate in (output_path, sidecar_path):
        if candidate.exists():
            raise FileExistsError(f"Average-volume export already exists: {candidate}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.parent / f".{output_path.name}.{uuid4().hex}.tmp"
    output_written = False

    source = np.load(source_path, mmap_mode="r", allow_pickle=False)
    try:
        if source.ndim != 3 or tuple(source.shape) != geometry.geometry.shape:
            raise ValueError("Average array shape does not match run-manifest geometry.")
        target_dtype, nrrd_type = _nrrd_dtype(source.dtype)
        header = _nrrd_header(geometry, nrrd_type=nrrd_type)
        with temporary_path.open("xb") as stream:
            stream.write(header)
            total = source.shape[2]
            for index in range(total):
                if cancellation_check is not None and cancellation_check():
                    raise RuntimeError("Average-volume NRRD export cancelled.")
                # NRRD axis 0 is fastest. A single AP/DV plane in Fortran
                # order preserves the declared AP, DV, ML axis sequence.
                plane = np.asarray(source[:, :, index], dtype=target_dtype)
                stream.write(plane.tobytes(order="F"))
                if progress_callback is not None:
                    progress_callback(index + 1, total)
        temporary_path.replace(output_path)
        output_written = True
    finally:
        _close_memmap(source)
        temporary_path.unlink(missing_ok=True)

    try:
        sidecar = artifact_manifest(
            artifact_type="registered_average_projection_nrrd",
            source_run_id=manifest["run_id"],
            statistic=statistic,
            coordinate_convention=COORDINATE_CONVENTION,
            geometry=geometry.to_dict(),
            source={
                "path": source_record["path"],
                "size_bytes": source_record["size_bytes"],
                "sha256": source_record["sha256"],
                "run_manifest": run_manifest_path.name,
                "run_manifest_sha256": file_sha256(run_manifest_path),
            },
            output={
                "path": output_path.name,
                "size_bytes": output_path.stat().st_size,
                "sha256": file_sha256(output_path),
                "encoding": "raw",
            },
        )
        write_json_immutable(sidecar_path, sidecar)
    except Exception:
        sidecar_path.unlink(missing_ok=True)
        if output_written:
            output_path.unlink(missing_ok=True)
        raise
    return AverageNrrdExport(
        statistic=statistic,
        nrrd_path=output_path,
        manifest_path=sidecar_path,
        source_array_path=source_path,
    )


def _validated_average_source(
    manifest: object,
    *,
    manifest_path: Path,
    statistic: str,
) -> tuple[Path, Mapping[str, object], VolumeGeometry]:
    if not isinstance(manifest, Mapping):
        raise ValueError("Average run manifest must be an object.")
    if manifest.get("schema") != RUN_SCHEMA:
        raise ValueError("Unsupported average run-manifest schema.")
    if manifest.get("operation") != "registered-average-projection-volume":
        raise ValueError("Manifest is not a registered average-volume run.")
    if not verify_manifest_integrity(manifest):
        raise ValueError("Average run-manifest checksum mismatch.")
    if manifest.get("coordinate_convention") != COORDINATE_CONVENTION:
        raise ValueError("Average run manifest uses an incompatible coordinate convention.")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("Average run manifest has no run identifier.")
    parameters = manifest.get("parameters")
    if not isinstance(parameters, Mapping) or parameters.get("file_base") != "..":
        raise ValueError("Average run manifest has an unsupported file base.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("Average run-manifest outputs must be a list.")
    matches = [
        record
        for record in outputs
        if isinstance(record, Mapping) and record.get("role") == statistic
    ]
    if len(matches) != 1:
        raise ValueError(f"Average run manifest must contain one {statistic!r} output.")
    record = matches[0]
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("Average output record has no path.")
    base_dir = manifest_path.parent.parent.resolve()
    source_path = (base_dir / raw_path).resolve()
    try:
        source_path.relative_to(base_dir)
    except ValueError as error:
        raise ValueError(f"Average output path escapes the cohort: {raw_path}") from error
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if source_path.stat().st_size != record.get("size_bytes"):
        raise ValueError(f"Average output size mismatch: {raw_path}")
    if file_sha256(source_path) != record.get("sha256"):
        raise ValueError(f"Average output checksum mismatch: {raw_path}")
    geometry = VolumeGeometry.from_dict(manifest.get("atlas"))
    return source_path, record, geometry


def _nrrd_dtype(dtype: np.dtype) -> tuple[np.dtype, str]:
    dtype = np.dtype(dtype)
    if dtype.kind != "f" or dtype.itemsize not in (4, 8):
        raise ValueError("Average NRRD export supports only float32 and float64 arrays.")
    if dtype.itemsize == 4:
        return np.dtype("<f4"), "float"
    return np.dtype("<f8"), "double"


def _nrrd_header(geometry: VolumeGeometry, *, nrrd_type: str) -> bytes:
    if any(character in geometry.space for character in "\r\n"):
        raise ValueError("NRRD space contains an invalid newline.")
    atlas = geometry.geometry
    direction = tuple(atlas.direction[row * 3 : row * 3 + 3] for row in range(3))
    vectors = tuple(
        tuple(direction[row][column] * atlas.spacing_um[column] for row in range(3))
        for column in range(3)
    )

    def number(value: float) -> str:
        if not math.isfinite(value):
            raise ValueError("NRRD geometry must contain finite values.")
        return format(value, ".17g")

    directions = " ".join(
        "(" + ",".join(number(component) for component in vector) + ")"
        for vector in vectors
    )
    origin = "(" + ",".join(number(value) for value in atlas.origin_um) + ")"
    header = "\n".join(
        (
            "NRRD0004",
            "# Generated by Neuroglobe registered average-volume export",
            f"type: {nrrd_type}",
            "dimension: 3",
            f"space: {geometry.space}",
            f"sizes: {atlas.shape[0]} {atlas.shape[1]} {atlas.shape[2]}",
            f"space directions: {directions}",
            "kinds: domain domain domain",
            "endian: little",
            "encoding: raw",
            f"space origin: {origin}",
            "",
            "",
        )
    )
    return header.encode("ascii")


def _close_memmap(array: np.ndarray) -> None:
    if isinstance(array, np.memmap):
        mapping = getattr(array, "_mmap", None)
        if mapping is not None:
            mapping.close()
