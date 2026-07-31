import numpy as np
import pytest

from neuroglobe.core.coordinates import AtlasGeometry
from neuroglobe.core.validation import (
    dice_coefficient,
    landmark_errors_um,
    make_asymmetric_phantom,
    validate_binary_alignment,
)


def test_asymmetric_phantom_identity_is_a_gold_standard_pass():
    phantom = make_asymmetric_phantom()

    result = validate_binary_alignment(
        phantom.mask,
        phantom.mask.copy(),
        phantom.geometry,
        maximum_hausdorff_um=0.0,
        maximum_centroid_error_um=0.0,
    )

    assert result.passed
    assert result.dice == 1.0
    assert result.hausdorff_um == 0.0
    assert result.centroid_error_um == 0.0


def test_asymmetric_phantom_detects_ml_flip():
    phantom = make_asymmetric_phantom()
    flipped = np.flip(phantom.mask, axis=2)

    result = validate_binary_alignment(phantom.mask, flipped, phantom.geometry)

    assert not result.passed
    assert result.dice < 0.5
    assert result.hausdorff_um >= phantom.geometry.spacing_um[2]


def test_physical_metrics_detect_header_only_translation():
    phantom = make_asymmetric_phantom()
    translated_geometry = AtlasGeometry.from_values(
        phantom.geometry.shape,
        phantom.geometry.spacing_um,
        (
            phantom.geometry.origin_um[0] + 100.0,
            phantom.geometry.origin_um[1],
            phantom.geometry.origin_um[2],
        ),
    )

    result = validate_binary_alignment(
        phantom.mask,
        phantom.mask.copy(),
        phantom.geometry,
        translated_geometry,
    )

    assert result.dice == 1.0
    assert result.hausdorff_um == pytest.approx(100.0)
    assert result.centroid_error_um == pytest.approx(100.0)
    assert not result.passed


def test_landmarks_include_spacing_origin_and_direction():
    geometry = AtlasGeometry.from_values(
        (3, 4, 5),
        (10, 20, 30),
        (100, 200, 300),
        (0, 0, 1, 0, 1, 0, -1, 0, 0),
    )
    assert geometry.index_to_physical((1, 2, 3)) == (190.0, 240.0, 290.0)

    errors = landmark_errors_um(
        {"known": (1, 2, 3)},
        {"known": (1, 2, 3)},
        geometry,
    )
    assert errors == {"known": 0.0}


def test_empty_masks_have_defined_dice():
    empty = np.zeros((2, 2, 2), dtype=bool)
    assert dice_coefficient(empty, empty) == 1.0
