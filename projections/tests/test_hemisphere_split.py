import pytest


pytestmark = [
    pytest.mark.gui,
    pytest.mark.integration,
    pytest.mark.skip(reason="Interactive BrainRender acceptance test; run manually."),
]


def test_split_rendering_interactive():
    """Reserved for the manual pixel/mesh hemisphere acceptance test."""
