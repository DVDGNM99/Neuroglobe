import json
from pathlib import Path

import numpy as np
import pytest

from neuroglobe.core.coordinates import AtlasGeometry
from neuroglobe.core.provenance import canonical_json_hash, verify_manifest_integrity
from neuroglobe.integration.geometry import VolumeGeometry, read_nrrd_geometry
from neuroglobe.projections.miner.average_export import export_average_nrrd
from neuroglobe.projections.miner.average_volume import (
    AverageVolumeProtocol,
    RegistrationQuality,
    aggregate_registered_volumes,
    create_registered_volume_manifest,
    load_registered_volume,
)
from neuroglobe.projections.miner.average_volume_cli import main


def _registered_subject(
    root: Path,
    subject_id: str,
    values: np.ndarray,
    *,
    quality: RegistrationQuality | None = None,
    geometry: VolumeGeometry | None = None,
) -> Path:
    subject_dir = root / subject_id
    subject_dir.mkdir(parents=True)
    volume_path = subject_dir / "registered.npy"
    volume = np.lib.format.open_memmap(
        volume_path,
        mode="w+",
        dtype=np.float32,
        shape=values.shape,
    )
    volume[...] = values
    volume.flush()
    del volume
    transform_path = subject_dir / "subject_to_reference.tfm"
    transform_path.write_text(f"transform for {subject_id}\n", encoding="utf-8")
    geometry = geometry or VolumeGeometry(
        geometry=AtlasGeometry.from_values(values.shape, (25.0, 25.0, 25.0)),
        space="left-posterior-superior",
    )
    manifest_path = subject_dir / "registered.manifest.json"
    return create_registered_volume_manifest(
        volume_path=volume_path,
        transform_path=transform_path,
        manifest_path=manifest_path,
        subject_id=subject_id,
        atlas_name="synthetic_allen_25um",
        reference_id="reference-v1",
        method="affine-plus-syn",
        interpolation="linear",
        quality=quality or RegistrationQuality(0.95, 100.0, 50.0),
        geometry=geometry,
    )


def _geometry_nrrd(path: Path, shape: tuple[int, int, int]) -> Path:
    path.write_text(
        "\n".join(
            (
                "NRRD0004",
                "type: float",
                "dimension: 3",
                "space: left-posterior-superior",
                f"sizes: {shape[0]} {shape[1]} {shape[2]}",
                "space directions: (25,0,0) (0,25,0) (0,0,25)",
                "encoding: raw",
                "space origin: (0,0,0)",
                "",
                "",
            )
        ),
        encoding="ascii",
    )
    return path


def test_registered_average_computes_sample_statistics_by_chunk(tmp_path):
    shape = (4, 3, 2)
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.full(shape, 1.0)),
        _registered_subject(tmp_path, "mouse-2", np.full(shape, 3.0)),
        _registered_subject(tmp_path, "mouse-3", np.full(shape, 5.0)),
    ]
    progress = []

    result = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
        maximum_working_bytes=3 * 2 * 8 * 6,
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    mean = np.load(result.mean_path, mmap_mode="r")
    variance = np.load(result.variance_path, mmap_mode="r")
    low = np.load(result.ci95_low_path, mmap_mode="r")
    high = np.load(result.ci95_high_path, mmap_mode="r")
    np.testing.assert_allclose(mean, 3.0)
    np.testing.assert_allclose(variance, 4.0)
    margin = 4.3026527297 * np.sqrt(4.0 / 3.0)
    np.testing.assert_allclose(low, 3.0 - margin, rtol=1e-6)
    np.testing.assert_allclose(high, 3.0 + margin, rtol=1e-6)
    assert result.chunk_depth == 1
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert verify_manifest_integrity(manifest)
    assert manifest["parameters"]["sample_size"] == 3
    assert manifest["parameters"]["variance"] == "sample variance (ddof=1)"
    assert manifest["parameters"]["confidence_interval"].startswith("two-sided")
    assert manifest["parameters"]["file_base"] == ".."
    assert all(not Path(record["path"]).is_absolute() for record in manifest["inputs"])


def test_average_excludes_failed_registration_qc_and_records_reason(tmp_path):
    shape = (2, 2, 2)
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.full(shape, 2.0)),
        _registered_subject(tmp_path, "mouse-2", np.full(shape, 4.0)),
        _registered_subject(
            tmp_path,
            "mouse-low-qc",
            np.full(shape, 100.0),
            quality=RegistrationQuality(0.5, 900.0, 800.0),
        ),
    ]

    result = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
        protocol=AverageVolumeProtocol(min_subjects=2),
    )

    np.testing.assert_allclose(np.load(result.mean_path), 3.0)
    assert result.included_subjects == ("mouse-1", "mouse-2")
    assert result.excluded[0].subject_id == "mouse-low-qc"
    assert len(result.excluded[0].reasons) == 3
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["parameters"]["excluded_subjects"][0]["subject_id"] == "mouse-low-qc"


def test_average_refuses_mixed_registered_geometry(tmp_path):
    first = _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2)))
    different_geometry = VolumeGeometry(
        geometry=AtlasGeometry.from_values((2, 2, 2), (50.0, 25.0, 25.0)),
        space="left-posterior-superior",
    )
    second = _registered_subject(
        tmp_path,
        "mouse-2",
        np.ones((2, 2, 2)),
        geometry=different_geometry,
    )

    with pytest.raises(ValueError, match="geometry mismatch"):
        aggregate_registered_volumes(
            (first, second),
            output_dir=tmp_path / "average",
        )


def test_registered_manifest_detects_modified_volume(tmp_path):
    manifest = _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2)))
    value = np.load(tmp_path / "mouse-1" / "registered.npy", mmap_mode="r+")
    value[0, 0, 0] = 42
    value.flush()
    del value

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_registered_volume(manifest)


def test_average_rejects_duplicate_subjects(tmp_path):
    first = _registered_subject(tmp_path, "first", np.ones((2, 2, 2)))
    second = _registered_subject(tmp_path, "second", np.ones((2, 2, 2)))
    second_value = json.loads(second.read_text(encoding="utf-8"))
    second_value["subject_id"] = "first"
    second_value.pop("manifest_sha256")
    second_value["manifest_sha256"] = canonical_json_hash(second_value, length=64)
    second.write_text(json.dumps(second_value), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate subject"):
        aggregate_registered_volumes(
            (first, second),
            output_dir=tmp_path / "average",
        )


def test_cancelled_average_removes_temporary_outputs(tmp_path):
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2))),
        _registered_subject(tmp_path, "mouse-2", np.ones((2, 2, 2))),
    ]
    output_dir = tmp_path / "average"

    with pytest.raises(RuntimeError, match="cancelled"):
        aggregate_registered_volumes(
            manifests,
            output_dir=output_dir,
            cancellation_check=lambda: True,
        )

    assert not list(output_dir.glob("*.npy"))
    assert not list(output_dir.glob(".*.tmp.npy"))


def test_average_volume_cli_help_is_dependency_light(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    assert "registration contracts" in capsys.readouterr().out


def test_average_volume_cli_creates_registration_contract(tmp_path, capsys):
    shape = (2, 2, 2)
    volume_path = tmp_path / "registered.npy"
    volume = np.lib.format.open_memmap(
        volume_path, mode="w+", dtype=np.float32, shape=shape
    )
    volume[...] = 1.0
    volume.flush()
    del volume
    transform = tmp_path / "transform.tfm"
    transform.write_text("identity for synthetic fixture\n", encoding="utf-8")
    geometry_nrrd = _geometry_nrrd(tmp_path / "reference.nrrd", shape)
    output = tmp_path / "registered.manifest.json"

    assert main(
        [
            "register",
            str(volume_path),
            "--transform",
            str(transform),
            "--geometry-nrrd",
            str(geometry_nrrd),
            "--output",
            str(output),
            "--subject-id",
            "mouse-1",
            "--atlas",
            "synthetic",
            "--reference-id",
            "reference-v1",
            "--method",
            "affine",
            "--dice",
            "0.95",
            "--hausdorff-um",
            "100",
            "--landmark-rmse-um",
            "50",
        ]
    ) == 0

    assert load_registered_volume(output).subject_id == "mouse-1"
    assert "manifest written" in capsys.readouterr().out


def test_average_export_preserves_geometry_and_voxel_axis_order(tmp_path):
    shape = (3, 2, 2)
    first_values = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    second_values = first_values + 2.0
    manifests = [
        _registered_subject(tmp_path, "mouse-1", first_values),
        _registered_subject(tmp_path, "mouse-2", second_values),
    ]
    average = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
    )

    exported = export_average_nrrd(
        average.manifest_path,
        statistic="mean",
        output_path=tmp_path / "average" / "mean.nrrd",
    )

    geometry = read_nrrd_geometry(exported.nrrd_path)
    assert geometry.geometry == load_registered_volume(manifests[0]).geometry.geometry
    payload = exported.nrrd_path.read_bytes()
    boundary = payload.index(b"\n\n") + 2
    restored = np.frombuffer(payload[boundary:], dtype="<f4").reshape(shape, order="F")
    np.testing.assert_array_equal(restored, first_values + 1.0)
    sidecar = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    assert verify_manifest_integrity(sidecar)
    assert sidecar["coordinate_convention"].endswith("units=um")


def test_average_export_rejects_modified_statistic_array(tmp_path):
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2))),
        _registered_subject(tmp_path, "mouse-2", np.full((2, 2, 2), 3.0)),
    ]
    average = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
    )
    mean = np.load(average.mean_path, mmap_mode="r+")
    mean[0, 0, 0] = 99
    mean.flush()
    del mean

    with pytest.raises(ValueError, match="checksum mismatch"):
        export_average_nrrd(
            average.manifest_path,
            statistic="mean",
            output_path=tmp_path / "average" / "mean.nrrd",
        )


def test_average_export_rejects_incompatible_coordinate_convention(tmp_path):
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2))),
        _registered_subject(tmp_path, "mouse-2", np.full((2, 2, 2), 3.0)),
    ]
    average = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
    )
    manifest = json.loads(average.manifest_path.read_text(encoding="utf-8"))
    manifest["coordinate_convention"] = "unknown"
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = canonical_json_hash(manifest, length=64)
    average.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="coordinate convention"):
        export_average_nrrd(
            average.manifest_path,
            statistic="mean",
            output_path=tmp_path / "average" / "mean.nrrd",
        )


def test_cancelled_average_export_removes_partial_nrrd(tmp_path):
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2))),
        _registered_subject(tmp_path, "mouse-2", np.full((2, 2, 2), 3.0)),
    ]
    average = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
    )
    output = tmp_path / "average" / "mean.nrrd"

    with pytest.raises(RuntimeError, match="cancelled"):
        export_average_nrrd(
            average.manifest_path,
            statistic="mean",
            output_path=output,
            cancellation_check=lambda: True,
        )

    assert not output.exists()
    assert not output.with_suffix(".manifest.json").exists()
    assert not list(output.parent.glob(".*.tmp"))


def test_average_volume_cli_exports_nrrd(tmp_path, capsys):
    manifests = [
        _registered_subject(tmp_path, "mouse-1", np.ones((2, 2, 2))),
        _registered_subject(tmp_path, "mouse-2", np.full((2, 2, 2), 3.0)),
    ]
    average = aggregate_registered_volumes(
        manifests,
        output_dir=tmp_path / "average",
    )
    output = tmp_path / "average" / "variance.nrrd"

    assert main(
        [
            "export-nrrd",
            str(average.manifest_path),
            "--statistic",
            "variance",
            "--output",
            str(output),
        ]
    ) == 0

    captured = capsys.readouterr()
    assert output.is_file()
    assert output.with_suffix(".manifest.json").is_file()
    assert "PROGRESS|2|2" in captured.out
    assert f"NRRD volume: {output}" in captured.out
