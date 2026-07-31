import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from neuroglobe.projections.viewer import rendering


def _render_modules(scene_class, *, load=None):
    brainrender = types.ModuleType("brainrender")
    brainrender.Scene = scene_class
    brainrender.settings = types.SimpleNamespace()
    actors = types.ModuleType("brainrender.actors")
    actors.Streamlines = MagicMock()
    vedo = types.ModuleType("vedo")
    vedo.Text2D = MagicMock()
    vedo.LegendBox = MagicMock()
    vedo.Volume = MagicMock()
    vedo.load = load or MagicMock()
    return {
        "brainrender": brainrender,
        "brainrender.actors": actors,
        "vedo": vedo,
    }


def _engine():
    engine = rendering.RenderEngine.__new__(rendering.RenderEngine)
    engine.atlas_name = "test_atlas"
    engine.atlas = types.SimpleNamespace(
        annotation=types.SimpleNamespace(shape=(528, 320, 456)),
        resolution=(25, 25, 25),
    )
    engine.root_dir = Path(".")
    engine.default_scenes_dir = Path("scenes")
    return engine


def test_both_mode_splits_on_ml_axis():
    scene_class = MagicMock()
    scene = scene_class.return_value
    root_actor = MagicMock()
    left_actor = MagicMock()
    right_actor = MagicMock()
    scene.add_brain_region.side_effect = [root_actor, left_actor, right_actor]

    with patch.dict(sys.modules, _render_modules(scene_class)):
        result = _engine().render_scene(
            [
                {
                    "acronym": "MOs",
                    "color_left": "#ff0000",
                    "color_right": "#0000ff",
                }
            ],
            data_mode="Both",
            show_legend=False,
        )

    left_actor.cut_with_plane.assert_called_once_with(
        origin=(0, 0, 5700.0), normal=(0, 0, 1)
    )
    right_actor.cut_with_plane.assert_called_once_with(
        origin=(0, 0, 5700.0), normal=(0, 0, -1)
    )
    assert result.success


def test_vtk_tract_is_reported_as_loaded(tmp_path):
    scene_class = MagicMock()
    scene = scene_class.return_value
    scene.add_brain_region.side_effect = [MagicMock(), MagicMock()]
    tract_actor = MagicMock()
    load = MagicMock(return_value=tract_actor)
    tract_path = tmp_path / "tract.vtk"
    tract_path.touch()

    with patch.dict(sys.modules, _render_modules(scene_class, load=load)):
        result = _engine().render_scene(
            [{"acronym": "VISp", "color": "#ff0000"}],
            tract_file=tract_path,
            show_legend=False,
        )

    load.assert_called_once_with(str(tract_path))
    assert result.success
    assert result.tract_loaded


def test_enabled_legend_receives_rendered_region_actors():
    scene_class = MagicMock()
    scene = scene_class.return_value
    root_actor = MagicMock()
    region_actor = MagicMock()
    scene.add_brain_region.side_effect = [root_actor, region_actor]
    modules = _render_modules(scene_class)

    with patch.dict(sys.modules, modules):
        result = _engine().render_scene(
            [{"acronym": "VISp", "color": "#ff0000"}],
            show_legend=True,
        )

    modules["vedo"].LegendBox.assert_called_once()
    assert modules["vedo"].LegendBox.call_args.kwargs["entries"] == [region_actor]
    assert result.success
