import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

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
@patch('src.viewer.filter_tracts.merge')
def test_run_filter_flow(mock_merge, mock_volume, mock_atlas, tmp_path):
    # Setup Mocks
    mock_bg = mock_atlas.return_value
    mock_bg.mesh_from_structure.return_value = MagicMock() # Mesh object
    
    mock_vol_instance = mock_volume.return_value
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
                mock_merge.assert_called()
