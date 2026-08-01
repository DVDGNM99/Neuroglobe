"""Registration-gated, bounded-memory average projection volumes."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping
from uuid import uuid4

import numpy as np

from neuroglobe.core.provenance import (
    COORDINATE_CONVENTION,
    canonical_json_hash,
    file_record,
    file_sha256,
    run_manifest,
    verify_manifest_integrity,
    write_json_immutable,
)
from neuroglobe.integration.geometry import (
    VolumeGeometry,
    geometry_identity_errors,
)


REGISTERED_VOLUME_SCHEMA = "neuroglobe.registered-volume/v1"
DEFAULT_WORKING_MEMORY_BYTES = 64 * 1024 * 1024
_T_CRITICAL_95 = (
    0.0,
    12.7062047364,
    4.3026527297,
    3.1824463053,
    2.7764451052,
    2.5705818356,
    2.4469118511,
    2.3646242510,
    2.3060041352,
    2.2621571629,
    2.2281388520,
    2.2009851601,
    2.1788128297,
    2.1603686565,
    2.1447866879,
    2.1314495456,
    2.1199052992,
    2.1098155778,
    2.1009220402,
    2.0930240544,
    2.0859634473,
    2.0796138447,
    2.0738730679,
    2.0686576104,
    2.0638985616,
    2.0595385528,
    2.0555294386,
    2.0518305165,
    2.0484071418,
    2.0452296421,
    2.0422724563,
)


@dataclass(frozen=True)
class RegistrationQuality:
    dice: float
    hausdorff_um: float
    landmark_rmse_um: float

    def __post_init__(self) -> None:
        values = (self.dice, self.hausdorff_um, self.landmark_rmse_um)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("Registration quality metrics must be finite.")
        if not 0.0 <= float(self.dice) <= 1.0:
            raise ValueError("Registration Dice must be between 0 and 1.")
        if self.hausdorff_um < 0 or self.landmark_rmse_um < 0:
            raise ValueError("Registration distance metrics cannot be negative.")


@dataclass(frozen=True)
class RegisteredVolume:
    subject_id: str
    atlas_name: str
    reference_id: str
    method: str
    interpolation: str
    quality: RegistrationQuality
    geometry: VolumeGeometry
    volume_path: Path
    transform_path: Path
    manifest_path: Path
    dtype: str


@dataclass(frozen=True)
class AverageVolumeProtocol:
    min_subjects: int = 2
    min_dice: float = 0.8
    max_hausdorff_um: float = 500.0
    max_landmark_rmse_um: float = 250.0
    require_nonnegative: bool = True
    output_dtype: str = "float32"

    def __post_init__(self) -> None:
        if self.min_subjects < 2:
            raise ValueError("Average volumes require at least two registered subjects.")
        if not 0.0 <= self.min_dice <= 1.0:
            raise ValueError("min_dice must be between 0 and 1.")
        if self.max_hausdorff_um < 0 or self.max_landmark_rmse_um < 0:
            raise ValueError("QC distance thresholds cannot be negative.")
        try:
            output_dtype = np.dtype(self.output_dtype)
        except TypeError as error:
            raise ValueError("output_dtype must be float32 or float64.") from error
        if output_dtype not in (np.dtype("float32"), np.dtype("float64")):
            raise ValueError("output_dtype must be float32 or float64.")


@dataclass(frozen=True)
class ExcludedRegisteredVolume:
    subject_id: str
    manifest_path: Path
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AverageVolumeResult:
    mean_path: Path
    variance_path: Path
    ci95_low_path: Path
    ci95_high_path: Path
    manifest_path: Path
    included_subjects: tuple[str, ...]
    excluded: tuple[ExcludedRegisteredVolume, ...]
    chunk_depth: int
    chunk_count: int
    t_critical: float


def create_registered_volume_manifest(
    *,
    volume_path: Path,
    transform_path: Path,
    manifest_path: Path,
    subject_id: str,
    atlas_name: str,
    reference_id: str,
    method: str,
    interpolation: str,
    quality: RegistrationQuality,
    geometry: VolumeGeometry,
) -> Path:
    """Bind one registered memory-mapped array to its transform and QC."""

    volume_path = Path(volume_path).resolve()
    transform_path = Path(transform_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    if not subject_id.strip() or not atlas_name.strip() or not reference_id.strip():
        raise ValueError("subject_id, atlas_name, and reference_id are required.")
    if not method.strip() or not interpolation.strip():
        raise ValueError("Registration method and interpolation are required.")
    if volume_path.suffix.lower() != ".npy":
        raise ValueError("Registered average-volume inputs must use .npy format.")
    if not transform_path.is_file():
        raise FileNotFoundError(transform_path)

    volume = np.load(volume_path, mmap_mode="r", allow_pickle=False)
    try:
        if volume.ndim != 3:
            raise ValueError("Registered volume must be three-dimensional.")
        if tuple(volume.shape) != geometry.geometry.shape:
            raise ValueError(
                f"Registered array shape {volume.shape} does not match "
                f"geometry {geometry.geometry.shape}."
            )
        dtype = volume.dtype.str
    finally:
        _close_memmap(volume)

    base_dir = manifest_path.parent
    fields: dict[str, object] = {
        "schema": REGISTERED_VOLUME_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "subject_id": subject_id,
        "atlas_name": atlas_name,
        "coordinate_convention": COORDINATE_CONVENTION,
        "geometry": geometry.to_dict(),
        "volume": {
            **file_record(volume_path, base_dir=base_dir, role="registered-volume"),
            "dtype": dtype,
            "shape": list(geometry.geometry.shape),
        },
        "registration": {
            "reference_id": reference_id,
            "method": method,
            "interpolation": interpolation,
            "transform": file_record(
                transform_path,
                base_dir=base_dir,
                role="registration-transform",
            ),
            "quality": asdict(quality),
        },
    }
    fields["manifest_sha256"] = canonical_json_hash(fields, length=64)
    write_json_immutable(manifest_path, fields)
    return manifest_path


def load_registered_volume(manifest_path: Path) -> RegisteredVolume:
    """Validate a registered-volume contract and every referenced file."""

    manifest_path = Path(manifest_path).resolve()
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or value.get("schema") != REGISTERED_VOLUME_SCHEMA:
        raise ValueError(f"Unsupported registered-volume schema: {manifest_path.name}")
    if not verify_manifest_integrity(value):
        raise ValueError(f"Registered-volume manifest checksum mismatch: {manifest_path.name}")
    if value.get("coordinate_convention") != COORDINATE_CONVENTION:
        raise ValueError("Registered volume uses an incompatible coordinate convention.")

    base_dir = manifest_path.parent
    volume_record = _require_mapping(value.get("volume"), "volume")
    registration = _require_mapping(value.get("registration"), "registration")
    transform_record = _require_mapping(registration.get("transform"), "transform")
    volume_path = _validate_file_record(volume_record, base_dir)
    transform_path = _validate_file_record(transform_record, base_dir)
    geometry = VolumeGeometry.from_dict(value.get("geometry"))

    volume = np.load(volume_path, mmap_mode="r", allow_pickle=False)
    try:
        expected_shape = tuple(int(item) for item in volume_record.get("shape", ()))
        if tuple(volume.shape) != expected_shape:
            raise ValueError(f"Registered array shape changed: {volume_path.name}")
        if tuple(volume.shape) != geometry.geometry.shape:
            raise ValueError("Registered array and geometry shapes differ.")
        if volume.dtype.str != volume_record.get("dtype"):
            raise ValueError(f"Registered array dtype changed: {volume_path.name}")
    finally:
        _close_memmap(volume)

    quality_value = _require_mapping(registration.get("quality"), "quality")
    try:
        quality = RegistrationQuality(
            dice=float(quality_value["dice"]),
            hausdorff_um=float(quality_value["hausdorff_um"]),
            landmark_rmse_um=float(quality_value["landmark_rmse_um"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Registered-volume quality metrics are invalid.") from error
    subject_id = str(value.get("subject_id", "")).strip()
    atlas_name = str(value.get("atlas_name", "")).strip()
    reference_id = str(registration.get("reference_id", "")).strip()
    method = str(registration.get("method", "")).strip()
    interpolation = str(registration.get("interpolation", "")).strip()
    if not all((subject_id, atlas_name, reference_id, method, interpolation)):
        raise ValueError("Registered-volume identity/registration fields are incomplete.")
    return RegisteredVolume(
        subject_id=subject_id,
        atlas_name=atlas_name,
        reference_id=reference_id,
        method=method,
        interpolation=interpolation,
        quality=quality,
        geometry=geometry,
        volume_path=volume_path,
        transform_path=transform_path,
        manifest_path=manifest_path,
        dtype=str(volume_record["dtype"]),
    )


def aggregate_registered_volumes(
    manifest_paths: Iterable[Path],
    *,
    output_dir: Path,
    output_prefix: str = "average_projection",
    protocol: AverageVolumeProtocol | None = None,
    maximum_working_bytes: int = DEFAULT_WORKING_MEMORY_BYTES,
    progress_callback: Callable[[int, int], None] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> AverageVolumeResult:
    """Compute mean, sample variance, and 95% CI from registered subjects."""

    protocol = protocol or AverageVolumeProtocol()
    if maximum_working_bytes <= 0:
        raise ValueError("maximum_working_bytes must be positive.")
    if not output_prefix or any(character in output_prefix for character in "\\/:"):
        raise ValueError("output_prefix must be a safe filename stem.")

    registered = tuple(load_registered_volume(path) for path in manifest_paths)
    if not registered:
        raise ValueError("At least one registered-volume manifest is required.")
    _validate_cohort_contract(registered)
    included, excluded = _apply_quality_control(registered, protocol)
    if len(included) < protocol.min_subjects:
        raise ValueError(
            f"Only {len(included)} subjects passed registration QC; "
            f"protocol requires {protocol.min_subjects}."
        )

    geometry = included[0].geometry
    shape = geometry.geometry.shape
    bytes_per_plane = int(np.prod(shape[1:], dtype=np.int64)) * 8 * 6
    if maximum_working_bytes < bytes_per_plane:
        raise ValueError(
            f"Working-memory budget must be at least {bytes_per_plane} bytes "
            "for one axis-0 plane."
        )
    chunk_depth = max(
        1,
        min(shape[0], maximum_working_bytes // bytes_per_plane),
    )
    chunk_count = (shape[0] + chunk_depth - 1) // chunk_depth
    t_critical = _student_t_critical_95(len(included))

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_root = output_dir.parent
    _validate_cohort_paths(registered, cohort_root)
    final_paths = {
        "mean": output_dir / f"{output_prefix}_mean.npy",
        "variance": output_dir / f"{output_prefix}_variance.npy",
        "ci95_low": output_dir / f"{output_prefix}_ci95_low.npy",
        "ci95_high": output_dir / f"{output_prefix}_ci95_high.npy",
    }
    manifest_path = output_dir / f"{output_prefix}.manifest.json"
    existing = [path for path in (*final_paths.values(), manifest_path) if path.exists()]
    if existing:
        raise FileExistsError(f"Average-volume output already exists: {existing[0]}")

    temporary_paths = {
        name: output_dir / f".{output_prefix}.{uuid4().hex}.{name}.tmp.npy"
        for name in final_paths
    }
    output_maps: dict[str, np.memmap] = {}
    input_maps: list[np.memmap] = []
    promoted_paths: list[Path] = []
    completed = False
    try:
        output_dtype = np.dtype(protocol.output_dtype)
        output_maps = {
            name: np.lib.format.open_memmap(
                path,
                mode="w+",
                dtype=output_dtype,
                shape=shape,
            )
            for name, path in temporary_paths.items()
        }
        input_maps = [
            np.load(item.volume_path, mmap_mode="r", allow_pickle=False)
            for item in included
        ]

        for chunk_index, start in enumerate(range(0, shape[0], chunk_depth), start=1):
            if cancellation_check is not None and cancellation_check():
                raise RuntimeError("Average-volume aggregation cancelled.")
            stop = min(start + chunk_depth, shape[0])
            chunk = (slice(start, stop), slice(None), slice(None))
            chunk_shape = (stop - start, *shape[1:])
            mean = np.zeros(chunk_shape, dtype=np.float64)
            m2 = np.zeros(chunk_shape, dtype=np.float64)

            for count, (registered_item, source) in enumerate(
                zip(included, input_maps), start=1
            ):
                block = np.array(source[chunk], dtype=np.float64, copy=True)
                if not np.all(np.isfinite(block)):
                    raise ValueError(
                        f"Subject {registered_item.subject_id} contains non-finite voxels."
                    )
                if protocol.require_nonnegative and float(block.min()) < 0:
                    raise ValueError(
                        f"Subject {registered_item.subject_id} contains negative voxels."
                    )
                delta = block - mean
                mean += delta / count
                block -= mean
                delta *= block
                m2 += delta

            variance = m2 / (len(included) - 1)
            margin = np.sqrt(variance / len(included))
            margin *= t_critical
            output_maps["mean"][chunk] = mean
            output_maps["variance"][chunk] = variance
            output_maps["ci95_low"][chunk] = mean - margin
            output_maps["ci95_high"][chunk] = mean + margin
            if progress_callback is not None:
                progress_callback(chunk_index, chunk_count)

        _close_memmap(*output_maps.values())
        output_maps.clear()
        for name, temporary in temporary_paths.items():
            temporary.replace(final_paths[name])
            promoted_paths.append(final_paths[name])
        completed = True
    finally:
        _close_memmap(*output_maps.values(), *input_maps)
        if not completed:
            for path in temporary_paths.values():
                path.unlink(missing_ok=True)
            for path in promoted_paths:
                path.unlink(missing_ok=True)

    try:
        # Close the time-of-check/time-of-use window before publishing outputs.
        # A source or transform modified during aggregation invalidates the run.
        for item in registered:
            load_registered_volume(item.manifest_path)
        manifest = _average_run_manifest(
            included=included,
            excluded=excluded,
            protocol=protocol,
            geometry=geometry,
            final_paths=final_paths,
            cohort_root=cohort_root,
            chunk_depth=chunk_depth,
            chunk_count=chunk_count,
            t_critical=t_critical,
        )
        write_json_immutable(manifest_path, manifest)
    except Exception:
        manifest_path.unlink(missing_ok=True)
        for path in promoted_paths:
            path.unlink(missing_ok=True)
        raise
    return AverageVolumeResult(
        mean_path=final_paths["mean"],
        variance_path=final_paths["variance"],
        ci95_low_path=final_paths["ci95_low"],
        ci95_high_path=final_paths["ci95_high"],
        manifest_path=manifest_path,
        included_subjects=tuple(item.subject_id for item in included),
        excluded=excluded,
        chunk_depth=chunk_depth,
        chunk_count=chunk_count,
        t_critical=t_critical,
    )


def _validate_cohort_contract(registered: tuple[RegisteredVolume, ...]) -> None:
    subject_ids = [item.subject_id for item in registered]
    if len(subject_ids) != len(set(subject_ids)):
        raise ValueError("Registered cohort contains duplicate subject IDs.")
    reference = registered[0]
    for item in registered[1:]:
        if item.atlas_name != reference.atlas_name:
            raise ValueError("Registered cohort contains multiple atlases.")
        if item.reference_id != reference.reference_id:
            raise ValueError("Registered cohort contains multiple registration references.")
        if item.method != reference.method or item.interpolation != reference.interpolation:
            raise ValueError("Registered cohort uses inconsistent registration protocols.")
        errors = geometry_identity_errors(item.geometry, reference.geometry)
        if errors:
            raise ValueError(
                f"Registered geometry mismatch for {item.subject_id}: "
                + "; ".join(errors)
            )


def _apply_quality_control(
    registered: tuple[RegisteredVolume, ...],
    protocol: AverageVolumeProtocol,
) -> tuple[tuple[RegisteredVolume, ...], tuple[ExcludedRegisteredVolume, ...]]:
    included: list[RegisteredVolume] = []
    excluded: list[ExcludedRegisteredVolume] = []
    for item in registered:
        reasons = []
        if item.quality.dice < protocol.min_dice:
            reasons.append(f"dice {item.quality.dice} < {protocol.min_dice}")
        if item.quality.hausdorff_um > protocol.max_hausdorff_um:
            reasons.append(
                f"hausdorff_um {item.quality.hausdorff_um} "
                f"> {protocol.max_hausdorff_um}"
            )
        if item.quality.landmark_rmse_um > protocol.max_landmark_rmse_um:
            reasons.append(
                f"landmark_rmse_um {item.quality.landmark_rmse_um} "
                f"> {protocol.max_landmark_rmse_um}"
            )
        if reasons:
            excluded.append(
                ExcludedRegisteredVolume(
                    subject_id=item.subject_id,
                    manifest_path=item.manifest_path,
                    reasons=tuple(reasons),
                )
            )
        else:
            included.append(item)
    return tuple(included), tuple(excluded)


def _validate_cohort_paths(
    registered: tuple[RegisteredVolume, ...],
    cohort_root: Path,
) -> None:
    for item in registered:
        for path in (item.manifest_path, item.volume_path, item.transform_path):
            try:
                path.relative_to(cohort_root)
            except ValueError as error:
                raise ValueError(
                    f"Registered cohort input is outside output_dir.parent: {path}"
                ) from error


def _average_run_manifest(
    *,
    included: tuple[RegisteredVolume, ...],
    excluded: tuple[ExcludedRegisteredVolume, ...],
    protocol: AverageVolumeProtocol,
    geometry: VolumeGeometry,
    final_paths: Mapping[str, Path],
    cohort_root: Path,
    chunk_depth: int,
    chunk_count: int,
    t_critical: float,
) -> dict[str, object]:
    inputs = []
    for item in included:
        inputs.extend(
            (
                file_record(
                    item.manifest_path,
                    base_dir=cohort_root,
                    role=f"registration:{item.subject_id}",
                ),
                file_record(
                    item.volume_path,
                    base_dir=cohort_root,
                    role=f"volume:{item.subject_id}",
                ),
                file_record(
                    item.transform_path,
                    base_dir=cohort_root,
                    role=f"transform:{item.subject_id}",
                ),
            )
        )
    inputs.extend(
        file_record(
            item.manifest_path,
            base_dir=cohort_root,
            role=f"excluded-registration:{item.subject_id}",
        )
        for item in excluded
    )
    outputs = [
        file_record(path, base_dir=cohort_root, role=name)
        for name, path in final_paths.items()
    ]
    return run_manifest(
        "registered-average-projection-volume",
        parameters={
            "protocol": asdict(protocol),
            "file_base": "..",
            "included_subjects": [item.subject_id for item in included],
            "excluded_subjects": [
                {
                    "subject_id": item.subject_id,
                    "manifest": item.manifest_path.name,
                    "reasons": list(item.reasons),
                }
                for item in excluded
            ],
            "sample_size": len(included),
            "variance": "sample variance (ddof=1)",
            "confidence_interval": "two-sided 95% Student t interval",
            "t_critical": t_critical,
            "chunk_depth": chunk_depth,
            "chunk_count": chunk_count,
        },
        inputs=inputs,
        outputs=outputs,
        atlas={
            "name": included[0].atlas_name,
            "reference_id": included[0].reference_id,
            **geometry.to_dict(),
        },
        transformations=(
            {
                "subject_id": item.subject_id,
                "method": item.method,
                "interpolation": item.interpolation,
                "transform_sha256": file_sha256(item.transform_path),
                "quality": asdict(item.quality),
            }
            for item in included
        ),
        packages=("numpy",),
    )


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Registered-volume {field_name} must be an object.")
    return value


def _student_t_critical_95(sample_size: int) -> float:
    """Two-sided 95% t critical without adding SciPy to the core runtime."""

    degrees_of_freedom = sample_size - 1
    if degrees_of_freedom < 1:
        raise ValueError("Student t intervals require at least two subjects.")
    if degrees_of_freedom < len(_T_CRITICAL_95):
        return _T_CRITICAL_95[degrees_of_freedom]
    # Second-order expansion around the normal critical value. At df=30 this
    # differs from the tabulated value by less than 2e-5 and converges to z.
    z = 1.959963984540054
    df = float(degrees_of_freedom)
    return z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (
        96 * df**2
    )


def _validate_file_record(record: Mapping[str, object], base_dir: Path) -> Path:
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("Registered-volume file record has no path.")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise ValueError("Registered-volume file paths must be relative.")
    path = (base_dir / relative).resolve()
    try:
        path.relative_to(base_dir)
    except ValueError as error:
        raise ValueError(f"Registered-volume path escapes its directory: {raw_path}") from error
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != record.get("size_bytes"):
        raise ValueError(f"Registered file size mismatch: {raw_path}")
    if file_sha256(path) != record.get("sha256"):
        raise ValueError(f"Registered file checksum mismatch: {raw_path}")
    return path


def _close_memmap(*arrays: np.ndarray) -> None:
    for array in arrays:
        if isinstance(array, np.memmap):
            array.flush()
            mapping = getattr(array, "_mmap", None)
            if mapping is not None:
                mapping.close()
