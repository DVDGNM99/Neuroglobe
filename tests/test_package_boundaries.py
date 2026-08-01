from pathlib import Path

import neuroglobe
import neuroglobe.integration
from neuroglobe.projections.miner import aggregate


def test_imports_resolve_inside_current_checkout():
    checkout = Path(__file__).resolve().parents[1]
    for module in (neuroglobe, neuroglobe.integration, aggregate):
        Path(module.__file__).resolve().relative_to(checkout)
