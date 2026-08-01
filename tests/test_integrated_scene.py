import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from neuroglobe.core.provenance import (
    artifact_manifest,
    canonical_json_hash,
    verify_manifest_integrity,
)
from neuroglobe.integration.cli import main
from neuroglobe.integration.geometry import read_nrrd_geometry
from neuroglobe.integration.model import IntegratedSceneSpec, LayerKind
from neuroglobe.integration.rendering import IntegratedRenderEngine


def _write_nrrd(
    path: Path,
    *,
    shape: tuple[int, int, int],
    spacing: tuple[float, float, float],
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Path:
    # Spell out the identity vectors to make the test fixture transparent.
    directions = (
        f"({spacing[0]},0,0) (0,{spacing[1]},0) (0,0,{spacing[2]})"
    )
    header = "\n".join(
        (
            "NRRD0004",
            "type: uchar",
            "dimension: 3",
            "space: left-posterior-superior",
            f"sizes: {shape[0]} {shape[1]} {shape[2]}",
            f"space directions: {directions}",
            "kinds: domain domain domain",
            "encoding: raw",
            f"space origin: ({origin[0]},{origin[1]},{origin[2]})",
            "",
            "",
        )
    ).encode("ascii")
    path.write_bytes(header + b"\x00")
    return path


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    projection = _write_nrrd(
        tmp_path / "projection.nrrd",
        shape=(528, 320, 456),
        spacing=(25.0, 25.0, 25.0),
    )
    gene = _write_nrrd(
        tmp_path / "Htr1a_filtered.nrrd",
        shape=(67, 41, 58),
        spacing=(200.0, 200.0, 200.0),
    )
    return projection, gene


def _spec(tmp_path: Path) -> IntegratedSceneSpec:
    projection, gene = _sources(tmp_path)
    return IntegratedSceneSpec.compose(
        projection_volumes={"experiment-42": projection},
        gene_expression_volumes={"Htr1a": gene},
        regions=("PL",),
        base_dir=tmp_path,
    )


def test_nrrd_header_geometry_is_read_without_loading_payload(tmp_path):
    projection, _ = _sources(tmp_path)

    geometry = read_nrrd_geometry(projection)

    assert geometry.geometry.shape == (528, 320, 456)
    assert geometry.geometry.spacing_um == (25.0, 25.0, 25.0)
    assert geometry.geometry.direction == (
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


def test_integrated_spec_roundtrip_binds_sources_and_geometry(tmp_path):
    spec = _spec(tmp_path)
    path = spec.save(tmp_path / "integrated.json")

    restored = IntegratedSceneSpec.load(path)

    assert restored.scene_id == spec.scene_id
    assert [layer.kind for layer in restored.layers] == [
        LayerKind.REGION,
        LayerKind.PROJECTION_VOLUME,
        LayerKind.GENE_EXPRESSION,
    ]
    serialized = json.loads(path.read_text(encoding="utf-8"))
    assert serialized["layers"][1]["source"] == "projection.nrrd"
    assert len(serialized["layers"][1]["source_sha256"]) == 64


def test_integrated_spec_rejects_legacy_projection_geometry(tmp_path):
    projection = _write_nrrd(
        tmp_path / "legacy_projection.nrrd",
        shape=(456, 320, 528),
        spacing=(1.0, 1.0, 1.0),
    )
    _, gene = _sources(tmp_path)

    with pytest.raises(ValueError, match="outside the atlas frame"):
        IntegratedSceneSpec.compose(
            projection_volumes={"legacy": projection},
            gene_expression_volumes={"Htr1a": gene},
            base_dir=tmp_path,
        )


def test_integrated_spec_rejects_changed_source(tmp_path):
    spec = _spec(tmp_path)
    path = spec.save(tmp_path / "integrated.json")
    with (tmp_path / "projection.nrrd").open("ab") as stream:
        stream.write(b"changed")

    with pytest.raises(ValueError, match="source checksum mismatch"):
        IntegratedSceneSpec.load(path)


def test_integrated_spec_binds_provenance_sidecar(tmp_path):
    projection, gene = _sources(tmp_path)
    sidecar = gene.with_suffix(".manifest.json")
    sidecar.write_text(
        json.dumps(artifact_manifest(artifact_type="gene-volume")), encoding="utf-8"
    )
    spec = IntegratedSceneSpec.compose(
        projection_volumes={"experiment-42": projection},
        gene_expression_volumes={"Htr1a": gene},
        base_dir=tmp_path,
    )
    path = spec.save(tmp_path / "integrated.json")
    sidecar.write_text(sidecar.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="provenance file checksum mismatch"):
        IntegratedSceneSpec.load(path)


def test_integrated_spec_rejects_escaped_source_path(tmp_path):
    spec = _spec(tmp_path)
    path = spec.save(tmp_path / "integrated.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["layers"][1]["source"] = "../projection.nrrd"
    value.pop("manifest_sha256")
    value["manifest_sha256"] = canonical_json_hash(value, length=64)
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="escapes its base directory"):
        IntegratedSceneSpec.load(path)


def test_integrated_run_manifest_records_identity_frame(tmp_path):
    manifest = _spec(tmp_path).build_run_manifest()

    assert verify_manifest_integrity(manifest)
    assert manifest["operation"] == "integrated-projection-gene-expression-render"
    assert len(manifest["inputs"]) == 2
    assert manifest["transformations"][0]["name"] == "identity-physical-frame"


def test_cli_compose_and_validate_do_not_import_graphics(tmp_path, capsys):
    projection, gene = _sources(tmp_path)
    output = tmp_path / "integrated.json"
    graphics_before = {
        name: sys.modules.get(name) for name in ("brainrender", "vedo")
    }

    assert main(
        [
            "compose",
            "--output",
            str(output),
            "--projection",
            f"experiment-42={projection}",
            "--gene",
            f"Htr1a={gene}",
            "--region",
            "PL",
        ]
    ) == 0
    assert {name: sys.modules.get(name) for name in graphics_before} == graphics_before
    assert main(["validate", str(output)]) == 0
    assert "Valid integrated scene" in capsys.readouterr().out


def test_renderer_adds_projection_and_gene_without_runtime_transform(tmp_path):
    spec = _spec(tmp_path)
    scene_class = MagicMock()
    scene = scene_class.return_value
    root_actor = MagicMock()
    region_actor = MagicMock()
    scene.add_brain_region.side_effect = [root_actor, region_actor]

    projection_actor = MagicMock()
    projection_volume = MagicMock()
    projection_volume.scalar_range.return_value = (0.0, 10.0)
    projection_volume.isosurface.return_value = projection_actor
    gene_actor = MagicMock()
    gene_volume = MagicMock()
    gene_volume.tonumpy.return_value = np.asarray([0.0, 1.0, 2.0, 4.0])
    gene_volume.legosurface.return_value = gene_actor
    volume_class = MagicMock(side_effect=[projection_volume, gene_volume])

    brainrender = types.ModuleType("brainrender")
    brainrender.Scene = scene_class
    vedo = types.ModuleType("vedo")
    vedo.LegendBox = MagicMock()
    vedo.Volume = volume_class

    with patch.dict(sys.modules, {"brainrender": brainrender, "vedo": vedo}):
        result = IntegratedRenderEngine(spec).render(validate_sources=False)

    assert result.success
    assert result.projections_rendered == 1
    assert result.genes_rendered == 1
    projection_volume.isosurface.assert_called_once_with(value=1.0)
    gene_volume.legosurface.assert_called_once()
    projection_actor.rotate_x.assert_not_called()
    projection_actor.rotate_y.assert_not_called()
    projection_actor.scale.assert_not_called()
    gene_actor.rotate_x.assert_not_called()
    gene_actor.rotate_y.assert_not_called()
    gene_actor.scale.assert_not_called()
    scene.render.assert_called_once_with(interactive=True, zoom=1.2)
