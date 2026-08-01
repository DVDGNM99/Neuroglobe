"""Versioned data model for projection/gene-expression scenes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping
from uuid import UUID, uuid4

from neuroglobe.core.coordinates import ALLEN_CCF_25UM
from neuroglobe.core.provenance import (
    COORDINATE_CONVENTION,
    canonical_json_hash,
    file_record,
    file_sha256,
    run_manifest,
    verify_manifest_integrity,
    write_json_atomic,
)
from neuroglobe.integration.geometry import (
    VolumeGeometry,
    geometry_compatibility_errors,
    geometry_identity_errors,
    read_nrrd_geometry,
)


INTEGRATED_SCENE_SCHEMA = "neuroglobe.integrated-scene/v1"
DEFAULT_ATLAS_SPACE = "left-posterior-superior"
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class LayerKind(str, Enum):
    REGION = "region"
    PROJECTION_VOLUME = "projection-volume"
    GENE_EXPRESSION = "gene-expression"


@dataclass(frozen=True)
class LayerStyle:
    color: str | None = None
    alpha: float = 0.6
    wireframe: bool = False
    projection_threshold_fraction: float = 0.1
    gene_percentile: float = 90.0

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.alpha) <= 1.0:
            raise ValueError("Layer alpha must be between 0 and 1.")
        if not 0.0 < float(self.projection_threshold_fraction) <= 1.0:
            raise ValueError("Projection threshold fraction must be in (0, 1].")
        if not 0.0 < float(self.gene_percentile) < 100.0:
            raise ValueError("Gene percentile must be in (0, 100).")

    def to_dict(self) -> dict[str, object]:
        return {
            "color": self.color,
            "alpha": float(self.alpha),
            "wireframe": self.wireframe,
            "projection_threshold_fraction": float(
                self.projection_threshold_fraction
            ),
            "gene_percentile": float(self.gene_percentile),
        }

    @classmethod
    def from_dict(cls, value: object) -> "LayerStyle":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValueError("Layer style must be an object.")
        return cls(
            color=str(value["color"]) if value.get("color") is not None else None,
            alpha=float(value.get("alpha", 0.6)),
            wireframe=bool(value.get("wireframe", False)),
            projection_threshold_fraction=float(
                value.get("projection_threshold_fraction", 0.1)
            ),
            gene_percentile=float(value.get("gene_percentile", 90.0)),
        )


@dataclass(frozen=True)
class SceneLayer:
    identifier: str
    kind: LayerKind
    label: str
    style: LayerStyle = field(default_factory=LayerStyle)
    acronym: str | None = None
    source: Path | None = None
    source_sha256: str | None = None
    geometry: VolumeGeometry | None = None
    provenance: Path | None = None
    provenance_sha256: str | None = None

    def __post_init__(self) -> None:
        if not _IDENTIFIER_PATTERN.fullmatch(self.identifier):
            raise ValueError(f"Invalid layer identifier: {self.identifier!r}")
        if not self.label.strip():
            raise ValueError("Layer label must not be empty.")
        if self.kind is LayerKind.REGION:
            if not self.acronym or not self.acronym.strip():
                raise ValueError("Region layers require an acronym.")
            if (
                self.source is not None
                or self.geometry is not None
                or self.provenance is not None
                or self.provenance_sha256 is not None
            ):
                raise ValueError("Region layers cannot declare spatial source metadata.")
            return
        if self.source is None or self.geometry is None:
            raise ValueError(f"{self.kind.value} layers require a source and geometry.")
        if self.source.suffix.lower() != ".nrrd":
            raise ValueError("Integrated spatial layers currently require .nrrd sources.")
        if not isinstance(self.source_sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.source_sha256
        ):
            raise ValueError("Spatial layers require a lowercase SHA-256 checksum.")
        if self.provenance is None and self.provenance_sha256 is not None:
            raise ValueError("A provenance checksum requires a provenance file.")
        if self.provenance is not None and (
            not isinstance(self.provenance_sha256, str)
            or not _SHA256_PATTERN.fullmatch(self.provenance_sha256)
        ):
            raise ValueError("Provenance files require a lowercase SHA-256 checksum.")

    @classmethod
    def region(
        cls,
        acronym: str,
        *,
        color: str = "lightgrey",
        alpha: float = 0.2,
        wireframe: bool = True,
    ) -> "SceneLayer":
        prefix = "region-"
        return cls(
            identifier=f"{prefix}{_safe_identifier(acronym, 80 - len(prefix))}",
            kind=LayerKind.REGION,
            label=acronym,
            acronym=acronym,
            style=LayerStyle(color=color, alpha=alpha, wireframe=wireframe),
        )

    @classmethod
    def volume(
        cls,
        kind: LayerKind,
        label: str,
        source: Path,
        *,
        style: LayerStyle | None = None,
        provenance: Path | None = None,
    ) -> "SceneLayer":
        if kind not in {LayerKind.PROJECTION_VOLUME, LayerKind.GENE_EXPRESSION}:
            raise ValueError(f"Unsupported volume layer kind: {kind.value}")
        source = Path(source).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        if provenance is None:
            candidate = source.with_suffix(".manifest.json")
            provenance = candidate if candidate.is_file() else None
        prefix = f"{kind.value}-"
        return cls(
            identifier=f"{prefix}{_safe_identifier(label, 80 - len(prefix))}",
            kind=kind,
            label=label,
            source=source,
            source_sha256=file_sha256(source),
            geometry=read_nrrd_geometry(source),
            provenance=Path(provenance).resolve() if provenance is not None else None,
            provenance_sha256=(
                file_sha256(Path(provenance).resolve())
                if provenance is not None
                else None
            ),
            style=style or LayerStyle(),
        )


@dataclass(frozen=True)
class IntegratedSceneSpec:
    atlas_name: str
    atlas_geometry: VolumeGeometry
    layers: tuple[SceneLayer, ...]
    scene_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    coordinate_convention: str = COORDINATE_CONVENTION
    base_dir: Path = field(default_factory=lambda: Path.cwd().resolve(), repr=False)

    def __post_init__(self) -> None:
        if not self.atlas_name.strip():
            raise ValueError("Atlas name must not be empty.")
        try:
            UUID(self.scene_id)
        except (ValueError, TypeError) as error:
            raise ValueError("scene_id must be a UUID.") from error
        if self.coordinate_convention != COORDINATE_CONVENTION:
            raise ValueError(
                f"Unsupported coordinate convention: {self.coordinate_convention!r}"
            )
        identifiers = [layer.identifier for layer in self.layers]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Integrated scene layer identifiers must be unique.")
        kinds = {layer.kind for layer in self.layers}
        if LayerKind.PROJECTION_VOLUME not in kinds or LayerKind.GENE_EXPRESSION not in kinds:
            raise ValueError(
                "An integrated scene requires at least one projection volume "
                "and one gene-expression volume."
            )
        for layer in self.layers:
            if layer.geometry is None:
                continue
            errors = geometry_compatibility_errors(layer.geometry, self.atlas_geometry)
            if errors:
                raise ValueError(
                    f"Layer {layer.identifier!r} is outside the atlas frame: "
                    + "; ".join(errors)
                )

    @classmethod
    def compose(
        cls,
        *,
        projection_volumes: Mapping[str, Path],
        gene_expression_volumes: Mapping[str, Path],
        regions: Iterable[str] = (),
        atlas_name: str = "allen_mouse_25um",
        base_dir: Path | None = None,
    ) -> "IntegratedSceneSpec":
        if atlas_name != "allen_mouse_25um":
            raise ValueError(
                "Only allen_mouse_25um has a validated integrated-scene geometry."
            )
        layers: list[SceneLayer] = [SceneLayer.region(acronym) for acronym in regions]
        layers.extend(
            SceneLayer.volume(LayerKind.PROJECTION_VOLUME, label, path)
            for label, path in projection_volumes.items()
        )
        layers.extend(
            SceneLayer.volume(
                LayerKind.GENE_EXPRESSION,
                label,
                path,
                style=LayerStyle(color="red", alpha=0.5, gene_percentile=90.0),
            )
            for label, path in gene_expression_volumes.items()
        )
        return cls(
            atlas_name=atlas_name,
            atlas_geometry=VolumeGeometry(
                geometry=ALLEN_CCF_25UM,
                space=DEFAULT_ATLAS_SPACE,
            ),
            layers=tuple(layers),
            base_dir=Path(base_dir or Path.cwd()).resolve(),
        )

    def validate_sources(self) -> None:
        errors: list[str] = []
        for layer in self.layers:
            if layer.source is None:
                continue
            if not layer.source.is_file():
                errors.append(f"{layer.identifier}: source is missing")
                continue
            if file_sha256(layer.source) != layer.source_sha256:
                errors.append(f"{layer.identifier}: source checksum mismatch")
            try:
                current_geometry = read_nrrd_geometry(layer.source)
                geometry_errors = geometry_identity_errors(
                    current_geometry, layer.geometry  # type: ignore[arg-type]
                )
                errors.extend(
                    f"{layer.identifier}: {message}" for message in geometry_errors
                )
            except ValueError as error:
                errors.append(f"{layer.identifier}: {error}")
            if layer.provenance is not None:
                try:
                    if file_sha256(layer.provenance) != layer.provenance_sha256:
                        errors.append(
                            f"{layer.identifier}: provenance file checksum mismatch"
                        )
                    manifest = json.loads(layer.provenance.read_text(encoding="utf-8"))
                    if not verify_manifest_integrity(manifest):
                        errors.append(f"{layer.identifier}: provenance checksum mismatch")
                    manifest_convention = manifest.get("coordinate_convention")
                    if manifest_convention not in (None, self.coordinate_convention):
                        errors.append(
                            f"{layer.identifier}: provenance coordinate convention mismatch"
                        )
                except (OSError, json.JSONDecodeError) as error:
                    errors.append(f"{layer.identifier}: invalid provenance: {error}")
        if errors:
            raise ValueError("Integrated scene validation failed: " + "; ".join(errors))

    def to_dict(self, *, base_dir: Path | None = None) -> dict[str, object]:
        root = Path(base_dir or self.base_dir).resolve()
        fields: dict[str, object] = {
            "schema": INTEGRATED_SCENE_SCHEMA,
            "scene_id": self.scene_id,
            "created_at": self.created_at,
            "atlas_name": self.atlas_name,
            "atlas_geometry": self.atlas_geometry.to_dict(),
            "coordinate_convention": self.coordinate_convention,
            "layers": [self._layer_to_dict(layer, root) for layer in self.layers],
        }
        fields["manifest_sha256"] = canonical_json_hash(fields, length=64)
        return fields

    def _layer_to_dict(self, layer: SceneLayer, root: Path) -> dict[str, object]:
        value: dict[str, object] = {
            "id": layer.identifier,
            "kind": layer.kind.value,
            "label": layer.label,
            "style": layer.style.to_dict(),
        }
        if layer.acronym is not None:
            value["acronym"] = layer.acronym
        if layer.source is not None:
            value["source"] = _relative_source(layer.source, root)
            value["source_sha256"] = layer.source_sha256
            value["geometry"] = layer.geometry.to_dict()  # type: ignore[union-attr]
        if layer.provenance is not None:
            value["provenance"] = _relative_source(layer.provenance, root)
            value["provenance_sha256"] = layer.provenance_sha256
        return value

    def save(self, path: Path) -> Path:
        path = Path(path).resolve()
        write_json_atomic(path, self.to_dict(base_dir=path.parent))
        return path

    @classmethod
    def load(cls, path: Path, *, validate_sources: bool = True) -> "IntegratedSceneSpec":
        path = Path(path).resolve()
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != INTEGRATED_SCENE_SCHEMA:
            raise ValueError("Unsupported integrated scene schema.")
        expected_digest = value.get("manifest_sha256")
        unsigned = {key: item for key, item in value.items() if key != "manifest_sha256"}
        if expected_digest != canonical_json_hash(unsigned, length=64):
            raise ValueError("Integrated scene manifest checksum mismatch.")
        base_dir = path.parent
        layers = tuple(_layer_from_dict(item, base_dir) for item in value.get("layers", ()))
        spec = cls(
            scene_id=str(value["scene_id"]),
            created_at=str(value["created_at"]),
            atlas_name=str(value["atlas_name"]),
            atlas_geometry=VolumeGeometry.from_dict(value["atlas_geometry"]),
            coordinate_convention=str(value["coordinate_convention"]),
            layers=layers,
            base_dir=base_dir,
        )
        if validate_sources:
            spec.validate_sources()
        return spec

    def build_run_manifest(self) -> dict[str, object]:
        inputs = []
        for layer in self.layers:
            if layer.source is not None:
                inputs.append(
                    file_record(
                        layer.source,
                        base_dir=self.base_dir,
                        role=f"{layer.kind.value}:{layer.identifier}",
                    )
                )
            if layer.provenance is not None:
                inputs.append(
                    file_record(
                        layer.provenance,
                        base_dir=self.base_dir,
                        role=f"provenance:{layer.identifier}",
                    )
                )
        return run_manifest(
            "integrated-projection-gene-expression-render",
            parameters={
                "scene_id": self.scene_id,
                "atlas_name": self.atlas_name,
                "layers": [
                    self._layer_to_dict(layer, self.base_dir) for layer in self.layers
                ],
            },
            inputs=inputs,
            atlas={
                "name": self.atlas_name,
                **self.atlas_geometry.to_dict(),
            },
            transformations=(
                {
                    "name": "identity-physical-frame",
                    "description": (
                        "No runtime scale, rotation, permutation, or translation; "
                        "NRRD physical AP/DV/ML geometry is used directly."
                    ),
                },
            ),
            packages=("brainrender", "vedo", "vtk"),
        )


def _safe_identifier(value: str, maximum_length: int) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    if not identifier:
        raise ValueError(f"Cannot derive an identifier from {value!r}.")
    return identifier[:maximum_length]


def _relative_source(path: Path, base_dir: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(base_dir).as_posix()
    except ValueError as error:
        raise ValueError(
            f"Integrated scene source must be inside its specification directory: {resolved}"
        ) from error


def _resolve_source(value: object, base_dir: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Layer source path must be a non-empty string.")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("Integrated scene paths must be relative.")
    resolved = (base_dir / relative).resolve()
    try:
        resolved.relative_to(base_dir)
    except ValueError as error:
        raise ValueError(f"Integrated scene path escapes its base directory: {value}") from error
    return resolved


def _layer_from_dict(value: object, base_dir: Path) -> SceneLayer:
    if not isinstance(value, Mapping):
        raise ValueError("Integrated scene layers must be objects.")
    try:
        kind = LayerKind(str(value["kind"]))
        source = (
            _resolve_source(value["source"], base_dir) if "source" in value else None
        )
        provenance = (
            _resolve_source(value["provenance"], base_dir)
            if "provenance" in value
            else None
        )
        return SceneLayer(
            identifier=str(value["id"]),
            kind=kind,
            label=str(value["label"]),
            acronym=str(value["acronym"]) if value.get("acronym") else None,
            source=source,
            source_sha256=(
                str(value["source_sha256"]) if value.get("source_sha256") else None
            ),
            geometry=(
                VolumeGeometry.from_dict(value["geometry"])
                if value.get("geometry") is not None
                else None
            ),
            provenance=provenance,
            provenance_sha256=(
                str(value["provenance_sha256"])
                if value.get("provenance_sha256")
                else None
            ),
            style=LayerStyle.from_dict(value.get("style")),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid integrated scene layer: {error}") from error
