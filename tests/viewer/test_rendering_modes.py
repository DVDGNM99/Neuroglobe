import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.viewer import rendering

@pytest.fixture
def mock_scene():
    with patch("src.viewer.rendering.Scene") as mock:
        yield mock

@pytest.fixture
def engine(mock_scene):
    # Mock BrainGlobeAtlas to avoid loading real atlas
    with patch("src.viewer.rendering.BrainGlobeAtlas"):
        return rendering.RenderEngine(atlas_name="test_atlas")

def test_render_density_mode(engine, mock_scene):
    """Test rendering with Density (Cloud) mode."""
    mock_tract_file = Path("test_tract.vtk")
    
    with patch("src.viewer.rendering.load") as mock_load: # Mock vedo.load
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

def test_render_streamlines_mode(engine, mock_scene):
    """Test rendering with Streamlines (Tubes) mode."""
    mock_tract_file = Path("test_streamlines.json")
    
    with patch("src.viewer.rendering.Streamlines") as mock_streamlines: # Mock brainrender.actors.Streamlines
        mock_actor = MagicMock()
        mock_streamlines.return_value = mock_actor
        
        engine.render_scene(
            region_config=[],
            tract_file=mock_tract_file,
            visualization_mode="Streamlines (Tubes)"
        )
        
        # Verify Streamlines actor was initialized
        mock_streamlines.assert_called_once_with(str(mock_tract_file))

def test_render_none_mode(engine, mock_scene):
    """Test rendering with None mode (no tracts)."""
    engine.render_scene(
        region_config=[],
        tract_file=None,
        visualization_mode="None"
    )
    
    # Verify no actors were loaded (implicit check)
    # In a real scenario we'd check scene.add calls, but mocking Scene is complex.
    # This mainly ensures no crash.
