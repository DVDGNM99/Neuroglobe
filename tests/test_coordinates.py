from neuroglobe.core.coordinates import (
    ALLEN_CCF_25UM,
    AtlasGeometry,
    Hemisphere,
    PhysicalAxis,
    injection_hemisphere,
    lateralization,
)


def test_ccf_midline_is_derived_from_ml_geometry():
    assert ALLEN_CCF_25UM.midpoint_um(PhysicalAxis.ML) == 5700.0
    custom = AtlasGeometry((10, 20, 30), (5, 6, 7), (1, 2, 3))
    assert custom.ml_midpoint_um == 108.0


def test_injection_hemisphere_has_explicit_unknown_midline():
    assert injection_hemisphere(2000) is Hemisphere.LEFT
    assert injection_hemisphere(9000) is Hemisphere.RIGHT
    assert injection_hemisphere(5700) is None
    assert injection_hemisphere(None) is None


def test_lateralization_handles_both_and_unknown():
    assert lateralization(1, Hemisphere.LEFT) == "Ipsilateral"
    assert lateralization(2, Hemisphere.LEFT) == "Contralateral"
    assert lateralization(3, Hemisphere.LEFT) == "Midline"
    assert lateralization(2, None) == "Unknown"
