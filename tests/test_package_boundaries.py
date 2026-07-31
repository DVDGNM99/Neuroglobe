from pathlib import Path

import neuroglobe
from neuroglobe.projections.miner import aggregate


def test_imports_resolve_inside_current_checkout():
    checkout = Path(__file__).resolve().parents[1]
    for module in (neuroglobe, aggregate):
        Path(module.__file__).resolve().relative_to(checkout)
