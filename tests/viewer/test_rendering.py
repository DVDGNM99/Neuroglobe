import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Mock vedo and brainrender BEFORE importing rendering
with patch.dict(sys.modules, {
    'vedo': MagicMock(),
    'brainrender': MagicMock(),
    'brainglobe_atlasapi': MagicMock()
}):
    from src.viewer import rendering

@patch('src.viewer.rendering.BrainGlobeAtlas')
@patch('src.viewer.rendering.Scene')
def test_render_engine_init(mock_scene, mock_atlas):
    engine = rendering.RenderEngine()
    assert engine is not None
    mock_atlas.assert_called_with("allen_mouse_25um")

@patch('src.viewer.rendering.BrainGlobeAtlas')
@patch('src.viewer.rendering.Scene')
def test_render_scene_logic(mock_scene, mock_atlas):
    # Setup
    engine = rendering.RenderEngine()
    mock_scene_instance = mock_scene.return_value
    
    # Test Data
    region_config = [{'acronym': 'VISp', 'color': '#FF0000'}]
    
    # Run
    engine.render_scene(region_config, tract_file=None)
    
    # Verify
    mock_scene_instance.add_brain_region.assert_any_call('root', alpha=0.05, color='grey')
    mock_scene_instance.add_brain_region.assert_any_call('VISp', alpha=0.5, color='#FF0000')
    mock_scene_instance.render.assert_called()
