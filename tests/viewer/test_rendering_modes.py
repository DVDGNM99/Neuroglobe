import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# Mock dependencies GLOBALLY and PERSISTENTLY
# preventing ImportErrors when 'patch' tries to reload them
sys.modules['vedo'] = MagicMock()
sys.modules['brainrender'] = MagicMock()
sys.modules['brainglobe_atlasapi'] = MagicMock()
sys.modules['brainrender.actors'] = MagicMock()
sys.modules['brainrender.settings'] = MagicMock()

# Now import the module under test
# Add src to path first just in case
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

with patch('src.viewer.rendering.load_visual_config', return_value={}):
    from src.viewer import rendering

@pytest.fixture
def mock_scene():
    with patch("src.viewer.rendering.Scene") as mock:
        yield mock

@pytest.fixture
def engine(mock_scene):
    # Mock Atlas
    with patch("src.viewer.rendering.BrainGlobeAtlas"):
        return rendering.RenderEngine(atlas_name="test_atlas")

def test_render_density_mode(engine, mock_scene, tmp_path):
    """Test rendering with Density (Cloud) mode."""
    # Create the file physically so .exists() passes
    mock_tract_file = tmp_path / "test_tract.vtk"
    mock_tract_file.touch()
    
    # Access the GLOBAL mock
    mock_load = sys.modules['vedo'].load
    mock_actor = MagicMock()
    mock_load.return_value = mock_actor
    
    engine.render_scene(
        region_config=[],
        tract_file=mock_tract_file,
        visualization_mode="Density (Cloud)"
    )
    
    # Verify load was called
    mock_load.assert_called_once_with(str(mock_tract_file))
    # Verify color was set to gray (default for density mesh)
    mock_actor.c.assert_called_with("gray")

def test_render_streamlines_mode(engine, mock_scene, tmp_path):
    """Test rendering with Streamlines (Tubes) mode."""
    # Create the file physically
    mock_tract_file = tmp_path / "test_streamlines.json"
    mock_tract_file.touch()
    
    # Access the GLOBAL mock that was set up at module level
    mock_class = sys.modules['brainrender.actors'].Streamlines
    mock_actor = MagicMock()
    mock_class.return_value = mock_actor
    
    engine.render_scene(
        region_config=[],
        tract_file=mock_tract_file,
        visualization_mode="Streamlines (Tubes)"
    )
    
    # Verify Streamlines actor was initialized
    mock_class.assert_called_once_with(str(mock_tract_file))

def test_render_none_mode(engine, mock_scene):
    """Test rendering with None mode (no tracts)."""
    engine.render_scene(
        region_config=[],
        tract_file=None,
        visualization_mode="None"
    )
    # Ensure no crash
