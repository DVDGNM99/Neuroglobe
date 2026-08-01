import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from neuroglobe.projections.miner import extract_tracts


def _write_test_nrrd(path: Path) -> None:
    path.write_bytes(
        b"\n".join(
            (
                b"NRRD0004",
                b"type: float",
                b"dimension: 3",
                b"space: left-posterior-superior",
                b"sizes: 2 2 2",
                b"space directions: (25,0,0) (0,25,0) (0,0,25)",
                b"encoding: raw",
                b"space origin: (0,0,0)",
                b"",
                b"",
            )
        )
        + bytes(2 * 2 * 2 * 4)
    )


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


def test_projection_energy_uses_supported_grid_api_and_atomic_nrrd(tmp_path):
    api = MagicMock()

    def download(experiment_id, images, resolution, save_file_path):
        assert experiment_id == 102
        assert images == ["projection_energy"]
        assert resolution == 25
        temporary = Path(save_file_path)
        assert temporary.name.startswith(".102_energy.")
        assert temporary.name.endswith(".tmp.nrrd")
        _write_test_nrrd(temporary)

    api.download_projection_grid_data.side_effect = download
    destination = tmp_path / "tracts" / "102_energy.nrrd"

    result = extract_tracts._download_projection_energy(api, 102, destination)

    assert result == destination
    assert destination.is_file()
    assert not list(destination.parent.glob(".*.tmp.nrrd"))
    api.download_projection_grid_data.assert_called_once()

    assert extract_tracts._download_projection_energy(api, 102, destination) == destination
    api.download_projection_grid_data.assert_called_once()


def test_invalid_projection_energy_download_removes_partial_file(tmp_path):
    api = MagicMock()
    api.download_projection_grid_data.side_effect = (
        lambda _experiment, _images, _resolution, path: Path(path).write_bytes(
            b"not an nrrd"
        )
    )
    destination = tmp_path / "tracts" / "103_energy.nrrd"

    with pytest.raises(ValueError, match="NRRD"):
        extract_tracts._download_projection_energy(api, 103, destination)

    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp.nrrd"))
