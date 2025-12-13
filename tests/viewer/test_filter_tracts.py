import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
import yaml
import numpy as np

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Mock dependencies GLOBALLY for this file
# We cannot use patch.dict context manager because it reverts sys.modules on exit,
# causing subsequent imports (by @patch decorators) to fail.
sys.modules['brainglobe_atlasapi'] = MagicMock()
sys.modules['vedo'] = MagicMock()

from src.viewer import filter_tracts

def test_load_targets_from_config(tmp_path):
    # Mock config file
    config_data = {
        "selection": {
            "custom_targets": ["VISp # Visual", "MOs"]
        }
    }
    config_file = tmp_path / "mining_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    # Patch CONFIG_PATH in the module
    with patch('src.viewer.filter_tracts.CONFIG_PATH', config_file):
        targets = filter_tracts.load_targets_from_config()
        assert targets == ["VISp", "MOs"]

def test_get_latest_tract_file(tmp_path):
    # Create dummy files
    d = tmp_path / "tracts"
    d.mkdir()
    (d / "old.nrrd").touch()
    # Make sure new file has newer mtime
    new_file = d / "new.nrrd"
    new_file.touch()
    
    # Patch DATA_DIR
    with patch('src.viewer.filter_tracts.DATA_DIR', d):
        latest = filter_tracts.get_latest_tract_file()
        assert latest.name == "new.nrrd"

@patch('src.viewer.filter_tracts.BrainGlobeAtlas')
@patch('src.viewer.filter_tracts.Volume')
def test_run_filter_flow(mock_volume, mock_atlas, tmp_path):
    # Setup Mocks
    mock_bg = mock_atlas.return_value
    mock_bg.mesh_from_structure.return_value = MagicMock() # Mesh object
    
    # Mock return value for get_structure_mask to avoid logic error
    mock_bg.get_structure_mask.return_value = np.zeros((10, 10, 10), dtype=bool)
    mock_bg.annotation.shape = (10, 10, 10)
    
    mock_vol_instance = mock_volume.return_value
    mock_vol_instance.tonumpy.return_value = np.zeros((10, 10, 10), dtype=float) # Match atlas shape
    mock_vol_instance.scalar_range.return_value = [0, 100]
    mock_vol_instance.isosurface.return_value = MagicMock() # Vol Mesh
    
    # Patch Globals
    with patch('src.viewer.filter_tracts.load_targets_from_config', return_value=['VISp']):
        with patch('src.viewer.filter_tracts.get_latest_tract_file', return_value=Path('dummy.nrrd')):
            with patch('src.viewer.filter_tracts.DATA_DIR', tmp_path):
                
                # Run
                filter_tracts.run_filter()
                
                # Verify
                mock_atlas.assert_called()
                mock_volume.assert_called()
