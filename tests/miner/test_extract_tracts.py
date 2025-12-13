import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.miner import extract_tracts

@patch('src.miner.extract_tracts.MouseConnectivityCache')
def test_fetch_and_process_tracts_nrrd(mock_mcc):
    # Setup
    experiment_id = 100
    mcc_instance = mock_mcc.return_value
    
    # Mock return value of get_projection_density
    # It returns (data_array, metadata_dict)
    mcc_instance.get_projection_density.return_value = (MagicMock(), {'resolution': [25, 25, 25]})

    # Mock SimpleITK (it's imported inside the function, so we need to mock it in sys.modules)
    with patch.dict(sys.modules, {'SimpleITK': MagicMock()}):
        # Run
        result = extract_tracts.fetch_and_process_tracts(experiment_id)
        
        # Verify
        assert result is True
        mcc_instance.get_projection_density.assert_called_with(experiment_id)

@patch('src.miner.extract_tracts.MouseConnectivityCache')
def test_fetch_and_process_tracts_mhd(mock_mcc):
    # Setup
    experiment_id = 101
    mcc_instance = mock_mcc.return_value
    
    # Mock projection density success
    mcc_instance.get_projection_density.return_value = (MagicMock(), {'resolution': [25, 25, 25]})
    
    # Mock API presence for energy download
    mcc_instance.api = MagicMock()
    mcc_instance.api.download_projection_energy = MagicMock()
    
    # Mock SimpleITK
    with patch.dict(sys.modules, {'SimpleITK': MagicMock()}):
        # Run
        result = extract_tracts.fetch_and_process_tracts(experiment_id)
        
        # Verify
        assert result is True
        mcc_instance.api.download_projection_energy.assert_called()
