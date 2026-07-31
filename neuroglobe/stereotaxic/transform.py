"""Versioned CCF-to-stereotaxic coordinate profiles.

Allen CCFv3 is an ex-cranio average template and has no intrinsic skull Bregma.
Profiles in this module are therefore literature mappings for visualization,
not surgical targeting calibrations for an individual animal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class StereotaxicCoordinate:
    ap_mm: float
    ml_mm: float
    dv_mm: float


@dataclass(frozen=True)
class StereotaxicTransform:
    profile_id: str
    bregma_ccf_um: tuple[float, float, float]
    reference_doi: str
    reference_note: str
    validated_for_surgery: bool = False

    def ccf_to_stereotaxic(
        self, coordinate_um: Iterable[float]
    ) -> StereotaxicCoordinate:
        """Convert CCF AP/DV/ML micrometres to Bregma-relative AP/ML/DV mm."""

        values = tuple(float(value) for value in coordinate_um)
        if len(values) != 3:
            raise ValueError("A CCF coordinate must contain AP, DV, and ML values.")
        ap_um, dv_um, ml_um = values
        bregma_ap, bregma_dv, bregma_ml = self.bregma_ccf_um
        return StereotaxicCoordinate(
            ap_mm=(bregma_ap - ap_um) / 1000.0,
            ml_mm=(ml_um - bregma_ml) / 1000.0,
            dv_mm=(dv_um - bregma_dv) / 1000.0,
        )

    def stereotaxic_to_ccf(
        self, coordinate: StereotaxicCoordinate
    ) -> tuple[float, float, float]:
        """Invert this profile into CCF AP/DV/ML micrometres."""

        bregma_ap, bregma_dv, bregma_ml = self.bregma_ccf_um
        return (
            bregma_ap - coordinate.ap_mm * 1000.0,
            bregma_dv + coordinate.dv_mm * 1000.0,
            bregma_ml + coordinate.ml_mm * 1000.0,
        )

    def provenance(self) -> dict[str, object]:
        return asdict(self)


# Conversion published with the Allen-CCF registered orofacial premotor atlas:
# AP_CCF = -AP_BREGMA*1000 + 5400; DV_CCF = DV_BREGMA*1000;
# ML_CCF = ML_BREGMA*1000 + 5700.
ELIFE_CCFV3_BREGMA_V1 = StereotaxicTransform(
    profile_id="elife-67291-ccfv3-bregma/v1",
    bregma_ccf_um=(5400.0, 0.0, 5700.0),
    reference_doi="10.7554/eLife.67291",
    reference_note=(
        "Published CCF conversion for visualization; Allen CCFv3 has no intrinsic "
        "skull Bregma and this profile is not calibrated for surgical targeting."
    ),
)

DEFAULT_STEREOTAXIC_TRANSFORM = ELIFE_CCFV3_BREGMA_V1
