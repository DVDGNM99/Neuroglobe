import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from neuroglobe.projections.viewer.controller import (
    TRACT_VISUALIZATION_MODES,
    TRACT_VOLUME_METRICS,
    ViewerController,
)


def _controller(tmp_path: Path) -> ViewerController:
    controller = ViewerController.__new__(ViewerController)
    controller.current_tract_id = 42
    controller.current_filtered_path = None
    controller.current_csv_path = None
    controller.current_csv_manifest = {}
    controller.current_scalar_min = 0.0
    controller.current_scalar_max = 1.0
    controller.tracts_dir = tmp_path / "tracts"
    controller.tracts_dir.mkdir()
    controller.scenes_dir = tmp_path / "scenes"
    controller.engine = MagicMock()
    controller.engine.render_scene.return_value = SimpleNamespace(
        success=True, errors=[]
    )
    return controller


def test_raw_energy_mode_selects_nrrd_volume(tmp_path):
    controller = _controller(tmp_path)
    energy = controller.tracts_dir / "42_energy.nrrd"
    energy.touch()

    success, _ = controller.render_scene(
        [{"acronym": "VISp", "color": "#ff0000"}],
        "Raw Volume",
        "ACA",
        True,
        metric="energy",
    )

    assert success
    assert controller.engine.render_scene.call_args.kwargs["tract_file"] == energy
    assert controller.engine.render_scene.call_args.kwargs["metadata"]["metric_used"] == "energy"


def test_filtered_mesh_rejects_different_metric(tmp_path):
    controller = _controller(tmp_path)
    filtered = controller.tracts_dir / "42_density_hash.vtk"
    filtered.touch()
    filtered.with_suffix(".manifest.json").write_text(
        json.dumps({"experiment_id": 42, "metric": "density"}),
        encoding="utf-8",
    )
    controller.current_filtered_path = filtered

    success, message = controller.render_scene(
        [{"acronym": "VISp", "color": "#ff0000"}],
        "Filtered Mesh",
        "ACA",
        True,
        metric="energy",
    )

    assert not success
    assert "metric mismatch" in message


def test_viewer_exposes_only_backed_tract_modes_and_metrics():
    assert TRACT_VISUALIZATION_MODES == ("None", "Raw Volume", "Filtered Mesh")
    assert TRACT_VOLUME_METRICS == ("density", "energy")


def test_unknown_visualization_mode_is_rejected_before_rendering(tmp_path):
    controller = _controller(tmp_path)

    success, message = controller.render_scene(
        [{"acronym": "VISp", "color": "#ff0000"}],
        "Streamlines (Tubes)",
        "ACA",
        True,
    )

    assert not success
    assert "Unsupported visualization mode" in message
    controller.engine.render_scene.assert_not_called()
