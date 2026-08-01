"""Opt-in scientific checks against an already downloaded Allen atlas."""

import os

import numpy as np
import pytest

from neuroglobe.core.coordinates import ALLEN_CCF_25UM


pytestmark = pytest.mark.integration


def _cached_allen_atlas():
    if os.environ.get("NEUROGLOBE_RUN_ATLAS_TESTS") != "1":
        pytest.skip("set NEUROGLOBE_RUN_ATLAS_TESTS=1 to use a local atlas cache")
    pytest.importorskip("brainglobe_atlasapi")
    from brainglobe_atlasapi import BrainGlobeAtlas
    from brainglobe_atlasapi.list_atlases import get_downloaded_atlases

    atlas_name = "allen_mouse_25um"
    if atlas_name not in get_downloaded_atlases():
        pytest.skip(f"{atlas_name} is not downloaded; integration test never fetches it")
    return BrainGlobeAtlas(atlas_name, check_latest=False)


def test_cached_allen_geometry_and_three_anatomical_landmarks():
    atlas = _cached_allen_atlas()

    assert tuple(atlas.annotation.shape) == ALLEN_CCF_25UM.shape
    assert tuple(float(value) for value in atlas.resolution) == ALLEN_CCF_25UM.spacing_um

    centroids = {}
    for acronym in ("PL", "CP", "VISp"):
        structure_id = atlas.structures[acronym]["id"]
        mask = np.asarray(atlas.get_structure_mask(structure_id), dtype=bool)
        assert mask.shape == ALLEN_CCF_25UM.shape
        assert np.any(mask)
        centroid_index = np.argwhere(mask).mean(axis=0)
        centroids[acronym] = ALLEN_CCF_25UM.index_to_physical(centroid_index)

    # These structures are anatomically distinct along AP in CCFv3.  The
    # ordering catches AP/ML permutations while avoiding fragile voxel counts.
    assert centroids["PL"][0] < centroids["CP"][0] < centroids["VISp"][0]
    for left, right in (("PL", "CP"), ("CP", "VISp"), ("PL", "VISp")):
        delta = np.subtract(centroids[left], centroids[right])
        assert float(np.sqrt(np.sum(delta * delta))) > 250.0
