import pytest

from neuroglobe.stereotaxic.transform import (
    DEFAULT_STEREOTAXIC_TRANSFORM,
    StereotaxicCoordinate,
)


def test_published_bregma_landmark_maps_to_zero():
    transform = DEFAULT_STEREOTAXIC_TRANSFORM

    coordinate = transform.ccf_to_stereotaxic((5400, 0, 5700))

    assert coordinate == StereotaxicCoordinate(ap_mm=0.0, ml_mm=0.0, dv_mm=0.0)
    assert not transform.validated_for_surgery


def test_published_elife_coordinate_equations():
    transform = DEFAULT_STEREOTAXIC_TRANSFORM

    coordinate = transform.ccf_to_stereotaxic((4400, 2000, 4200))

    assert coordinate.ap_mm == pytest.approx(1.0)
    assert coordinate.ml_mm == pytest.approx(-1.5)
    assert coordinate.dv_mm == pytest.approx(2.0)


def test_stereotaxic_round_trip_is_reversible():
    transform = DEFAULT_STEREOTAXIC_TRANSFORM
    source = (7250.0, 3150.0, 8125.0)

    restored = transform.stereotaxic_to_ccf(transform.ccf_to_stereotaxic(source))

    assert restored == pytest.approx(source)
    provenance = transform.provenance()
    assert provenance["profile_id"] == "elife-67291-ccfv3-bregma/v1"
    assert provenance["reference_doi"] == "10.7554/eLife.67291"
