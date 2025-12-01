import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.miner import extract_tracts

@patch('src.miner.extract_tracts.MouseConnectivityCache')
@patch('src.miner.extract_tracts.shutil.copy')
def test_fetch_and_process_tracts_nrrd(mock_copy, mock_mcc):
    # Setup
    experiment_id = 100
    
    # Mock glob to return a .nrrd file
    with patch('pathlib.Path.glob') as mock_glob:
        mock_glob.return_value = [Path('data/raw/experiment_100/density.nrrd')]
        
        # Mock exists to return True for experiment dir
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Run
            result = extract_tracts.fetch_and_process_tracts(experiment_id)
            
            # Verify
            assert result is True
            mock_copy.assert_called()

@patch('src.miner.extract_tracts.MouseConnectivityCache')
@patch('src.miner.extract_tracts.shutil.copy')
def test_fetch_and_process_tracts_mhd(mock_copy, mock_mcc):
    # Setup
    experiment_id = 101
    
    # Mock glob to return .mhd file (and empty .nrrd)
    with patch('pathlib.Path.glob') as mock_glob:
        def glob_side_effect(pattern):
            if pattern == "*.nrrd": return []
            if pattern == "*.mhd": return [Path('data/raw/experiment_101/density.mhd')]
            return []
        mock_glob.side_effect = glob_side_effect
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Mock file reading/writing for header patch
            with patch('builtins.open', mock_open(read_data="ElementDataFile = density.raw\nSomeOtherData")) as mock_file:
                
                # Run
                result = extract_tracts.fetch_and_process_tracts(experiment_id)
                
                # Verify
                assert result is True
                # Check if file was opened for writing (patching)
                assert mock_file.call_count >= 2 # Read + Write
