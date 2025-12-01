import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.miner import fetch

@pytest.fixture
def mock_mcc():
    with patch('src.miner.fetch.MouseConnectivityCache') as MockMCC:
        mock_instance = MockMCC.return_value
        yield mock_instance

def test_get_experiments_success(mock_mcc):
    # Setup mock
    mock_ontology = MagicMock()
    mock_ontology.get_structures_by_acronym.return_value = [{'id': 123, 'acronym': 'VISp'}]
    mock_mcc.get_structure_tree.return_value = mock_ontology
    
    mock_experiments = pd.DataFrame({
        'id': [1, 2],
        'gender': ['M', 'F']
    })
    mock_mcc.get_experiments.return_value = mock_experiments
    
    # Run
    experiments, mcc = fetch.get_experiments('VISp', Path('dummy/path'))
    
    # Verify
    assert len(experiments) == 2
    assert mcc == mock_mcc
    mock_ontology.get_structures_by_acronym.assert_called_with(['VISp'])
    mock_mcc.get_experiments.assert_called()

def test_get_experiments_invalid_acronym(mock_mcc):
    # Setup mock to raise IndexError (simulating not found)
    mock_ontology = MagicMock()
    mock_ontology.get_structures_by_acronym.side_effect = IndexError
    mock_mcc.get_structure_tree.return_value = mock_ontology
    
    # Run & Verify
    with pytest.raises(ValueError, match="not found in Allen Ontology"):
        fetch.get_experiments('INVALID', Path('dummy/path'))
