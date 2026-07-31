from uuid import UUID

import pytest

from neuroglobe.core.provenance import (
    ARTIFACT_SCHEMA,
    RUN_SCHEMA,
    artifact_manifest,
    file_record,
    run_manifest,
    verify_manifest_files,
    verify_manifest_integrity,
    write_json_immutable,
)


def test_artifact_manifest_has_uuid_versions_and_integrity():
    manifest = artifact_manifest(
        run_id="12345678-1234-5678-1234-567812345678",
        created_at="2026-07-31T00:00:00+00:00",
        artifact_type="test",
    )

    assert manifest["schema"] == ARTIFACT_SCHEMA
    assert UUID(manifest["run_id"])
    assert manifest["software"]["neuroglobe"] == "5.0.0"
    assert verify_manifest_integrity(manifest)

    manifest["artifact_type"] = "tampered"
    assert not verify_manifest_integrity(manifest)


def test_run_manifest_verifies_relative_files_and_detects_changes(tmp_path):
    source = tmp_path / "inputs" / "source.txt"
    source.parent.mkdir()
    source.write_text("stable input", encoding="utf-8")
    output = tmp_path / "outputs" / "result.txt"
    output.parent.mkdir()
    output.write_text("stable output", encoding="utf-8")

    manifest = run_manifest(
        "scientific-validation",
        run_id="12345678-1234-5678-1234-567812345678",
        created_at="2026-07-31T00:00:00+00:00",
        parameters={"minimum_dice": 0.99},
        inputs=[file_record(source, base_dir=tmp_path, role="reference")],
        outputs=[file_record(output, base_dir=tmp_path, role="metrics")],
        atlas={"name": "asymmetric-phantom", "resolution_um": [25, 40, 60]},
        transformations=[{"name": "identity", "version": 1}],
        git_commit="abc123",
    )

    assert manifest["schema"] == RUN_SCHEMA
    assert manifest["inputs"][0]["path"] == "inputs/source.txt"
    assert verify_manifest_files(manifest, base_dir=tmp_path) == ()

    output.write_text("changed output", encoding="utf-8")
    errors = verify_manifest_files(manifest, base_dir=tmp_path)
    assert "size mismatch: outputs/result.txt" in errors


def test_file_record_refuses_paths_outside_run_directory(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="outside base_dir"):
            file_record(outside, base_dir=tmp_path)
    finally:
        outside.unlink()


def test_immutable_manifest_cannot_be_overwritten(tmp_path):
    path = tmp_path / "run.json"
    write_json_immutable(path, {"schema": RUN_SCHEMA})

    with pytest.raises(FileExistsError):
        write_json_immutable(path, {"schema": "replacement"})
