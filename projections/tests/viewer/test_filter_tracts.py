import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from neuroglobe.projections.viewer import filter_tracts


def _dependency_modules(atlas_class, volume_class):
    atlas_module = types.ModuleType("brainglobe_atlasapi")
    atlas_module.BrainGlobeAtlas = atlas_class
    vedo_module = types.ModuleType("vedo")
    vedo_module.Volume = volume_class
    return {"brainglobe_atlasapi": atlas_module, "vedo": vedo_module}


def test_load_targets_from_config_deduplicates(tmp_path):
    config = tmp_path / "mining_config.yaml"
    config.write_text(
        """
experiment: {seed_acronym: VISp, target_regex: "*"}
processing: {metric: projection_density, aggregation_mode: mean}
quality_control: {min_injection_volume: 0, threshold_lower: 0}
selection:
  use_custom_targets: true
  custom_targets: ["VISp # Visual", MOs, VISp]
""",
        encoding="utf-8",
    )
    with patch.object(filter_tracts, "CONFIG_PATH", config):
        assert filter_tracts.load_targets_from_config() == ["VISp", "MOs"]


def test_run_filter_rejects_shape_mismatch(tmp_path):
    input_path = tmp_path / "input.nrrd"
    input_path.touch()
    atlas_class = MagicMock()
    atlas = atlas_class.return_value
    atlas.annotation.shape = (10, 10, 10)
    atlas.resolution = (25, 25, 25)
    volume_class = MagicMock()
    volume = volume_class.return_value
    volume.tonumpy.return_value = np.ones((9, 10, 10), dtype=np.float32)
    volume.spacing.return_value = (25, 25, 25)

    with patch.dict(sys.modules, _dependency_modules(atlas_class, volume_class)):
        with pytest.raises(filter_tracts.TractFilterError, match="shape mismatch"):
            filter_tracts.run_filter(
                input_path,
                tmp_path / "output.vtk",
                target_regions=["VISp"],
            )


def test_run_filter_rejects_all_invalid_regions(tmp_path):
    input_path = tmp_path / "input.nrrd"
    input_path.touch()
    atlas_class = MagicMock()
    atlas = atlas_class.return_value
    atlas.annotation.shape = (3, 3, 3)
    atlas.resolution = (25, 25, 25)
    atlas.structures = {}
    volume_class = MagicMock()
    volume = volume_class.return_value
    volume.tonumpy.return_value = np.ones((3, 3, 3), dtype=np.float32)
    volume.spacing.return_value = (25, 25, 25)

    with patch.dict(sys.modules, _dependency_modules(atlas_class, volume_class)):
        with pytest.raises(filter_tracts.TractFilterError, match="None of"):
            filter_tracts.run_filter(
                input_path,
                tmp_path / "output.vtk",
                target_regions=["INVALID"],
            )
