import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np

from neuroglobe.projections.miner import extract_tracts


def _allen_modules(cache_class):
    cache_module = types.ModuleType("allensdk.core.mouse_connectivity_cache")
    cache_module.MouseConnectivityCache = cache_class
    return {
        "allensdk": types.ModuleType("allensdk"),
        "allensdk.core": types.ModuleType("allensdk.core"),
        "allensdk.core.mouse_connectivity_cache": cache_module,
    }


def test_fetch_and_process_tracts_preserves_explicit_array_axis_order(tmp_path):
    cache_class = MagicMock()
    cache = cache_class.return_value
    data = np.zeros((4, 3, 2), dtype=np.float32)  # AP, DV, ML
    cache.get_projection_density.return_value = (data, {"resolution": [25, 25, 25]})
    simple_itk = MagicMock()

    with (
        patch.dict(sys.modules, _allen_modules(cache_class) | {"SimpleITK": simple_itk}),
        patch.object(extract_tracts, "RAW_DATA_DIR", tmp_path / "raw"),
        patch.object(extract_tracts, "DATA_RAW_PATH", tmp_path / "raw"),
        patch.object(extract_tracts, "TRACTS_DIR", tmp_path / "tracts"),
        patch.object(extract_tracts, "DATA_PROCESSED_TRACTS", tmp_path / "tracts"),
    ):
        assert extract_tracts.fetch_and_process_tracts(100) is True

    written_array = simple_itk.GetImageFromArray.call_args.args[0]
    assert written_array.shape == (2, 3, 4)  # SimpleITK Z, Y, X input
    simple_itk.GetImageFromArray.return_value.SetSpacing.assert_called_once_with(
        (25.0, 25.0, 25.0)
    )


def test_cached_allen_nrrd_is_copied_without_reconstruction(tmp_path):
    source = tmp_path / "raw" / "experiment_101" / "projection_density_25.nrrd"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"NRRD geometry and payload")
    destination = tmp_path / "tracts" / "101_density.nrrd"
    destination.parent.mkdir()

    extract_tracts._write_density_with_geometry(
        np.zeros((1, 1, 1)),
        {},
        source,
        destination,
    )
    assert destination.read_bytes() == source.read_bytes()
