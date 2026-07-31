"""Versioned, path-safe provenance records for Neuroglobe artifacts."""

from __future__ import annotations

import hashlib
import json
import platform
from importlib import metadata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4


ARTIFACT_SCHEMA = "neuroglobe.artifact/v2"
RUN_SCHEMA = "neuroglobe.run/v1"
COORDINATE_CONVENTION = "Allen CCF: x=AP, y=DV, z=ML; units=um"


def canonical_json_hash(value: Any, *, length: int = 12) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(path)


def write_json_immutable(path: Path, value: Any) -> None:
    """Create a JSON record exactly once and refuse accidental replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def software_versions(packages: Iterable[str] = ()) -> dict[str, str]:
    """Collect runtime/package versions without importing optional libraries."""

    versions = {"python": platform.python_version()}
    requested = tuple(dict.fromkeys(("neuroglobe", *packages)))
    for package in requested:
        if package == "neuroglobe":
            # The imported source tree is authoritative.  An environment may
            # still contain metadata from an older editable installation.
            from neuroglobe import __version__

            versions[package] = __version__
            continue
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return versions


def file_record(
    path: Path,
    *,
    base_dir: Path | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """Describe a file without leaking an absolute machine-specific path."""

    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if base_dir is None:
        display_path = resolved.name
    else:
        try:
            display_path = resolved.relative_to(Path(base_dir).resolve()).as_posix()
        except ValueError as error:
            raise ValueError(f"Artifact is outside base_dir: {resolved}") from error
    record: dict[str, Any] = {
        "path": display_path,
        "size_bytes": resolved.stat().st_size,
        "sha256": file_sha256(resolved),
    }
    if role is not None:
        record["role"] = role
    return record


def _manifest_with_digest(fields: Mapping[str, Any]) -> dict[str, Any]:
    manifest = dict(fields)
    manifest["manifest_sha256"] = canonical_json_hash(manifest, length=64)
    return manifest


def artifact_manifest(
    *,
    run_id: str | UUID | None = None,
    created_at: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build a self-identifying sidecar for one generated artifact."""

    manifest = {
        "schema": ARTIFACT_SCHEMA,
        "run_id": str(run_id or uuid4()),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "software": software_versions(),
        **fields,
    }
    return _manifest_with_digest(manifest)


def run_manifest(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    inputs: Iterable[Mapping[str, Any]] = (),
    outputs: Iterable[Mapping[str, Any]] = (),
    atlas: Mapping[str, Any] | None = None,
    transformations: Iterable[Mapping[str, Any]] = (),
    packages: Iterable[str] = (),
    git_commit: str | None = None,
    run_id: str | UUID | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a complete, versioned run record suitable for deterministic reruns."""

    if not operation.strip():
        raise ValueError("A provenance operation name is required.")
    manifest: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "run_id": str(run_id or uuid4()),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "coordinate_convention": COORDINATE_CONVENTION,
        "parameters": dict(parameters),
        "parameters_hash": canonical_json_hash(parameters, length=64),
        "inputs": [dict(record) for record in inputs],
        "outputs": [dict(record) for record in outputs],
        "software": software_versions(packages),
        "transformations": [dict(value) for value in transformations],
    }
    if atlas is not None:
        manifest["atlas"] = dict(atlas)
    if git_commit is not None:
        manifest["git_commit"] = git_commit
    return _manifest_with_digest(manifest)


def verify_manifest_integrity(manifest: Mapping[str, Any]) -> bool:
    """Verify the manifest's own canonical SHA-256 digest."""

    expected = manifest.get("manifest_sha256")
    if not isinstance(expected, str):
        return False
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return canonical_json_hash(unsigned, length=64) == expected


def verify_manifest_files(
    manifest: Mapping[str, Any],
    *,
    base_dir: Path,
) -> tuple[str, ...]:
    """Return reproducibility errors for missing, escaped, or modified files."""

    errors: list[str] = []
    base = Path(base_dir).resolve()
    for section in ("inputs", "outputs"):
        records = manifest.get(section, ())
        if not isinstance(records, list):
            errors.append(f"{section} must be a list")
            continue
        for record in records:
            if not isinstance(record, Mapping) or not isinstance(record.get("path"), str):
                errors.append(f"invalid {section} record")
                continue
            candidate = (base / record["path"]).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:
                errors.append(f"unsafe path: {record['path']}")
                continue
            if not candidate.is_file():
                errors.append(f"missing file: {record['path']}")
                continue
            if candidate.stat().st_size != record.get("size_bytes"):
                errors.append(f"size mismatch: {record['path']}")
                continue
            if file_sha256(candidate) != record.get("sha256"):
                errors.append(f"checksum mismatch: {record['path']}")
    if not verify_manifest_integrity(manifest):
        errors.append("manifest checksum mismatch")
    return tuple(errors)
