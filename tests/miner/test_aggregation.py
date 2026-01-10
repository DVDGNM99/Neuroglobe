import pandas as pd
import pytest
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# MOCK allensdk before import
sys.modules["allensdk"] = MagicMock()
sys.modules["allensdk.core"] = MagicMock()
sys.modules["allensdk.core.mouse_connectivity_cache"] = MagicMock()

from src.miner.aggregate import process_aggregation

def test_aggregation_mixed_experiments():
    """
    Test aggregation with two experiments:
    Exp 1: Left Injection (x=2000)
    Exp 2: Right Injection (x=9000)
    """
    
    # 1. Setup Mock Data
    experiments_data = {
        'id': [100, 200],
        'injection_x': [2000, 9000] # 2000=Left, 9000=Right
    }
    experiments_df = pd.DataFrame(experiments_data)
    
    # Unionizes: Let's pretend we have one target region "MR" (Model Region)
    # Hemi 1 = Left, Hemi 2 = Right
    unionizes_data = [
        # Exp 1 (Left Inj) -> Target in Left (Ipsi)
        {'experiment_id': 100, 'structure_id': 5, 'hemisphere_id': 1, 'projection_density': 10.0, 'is_injection': False},
        # Exp 1 (Left Inj) -> Target in Right (Contra)
        {'experiment_id': 100, 'structure_id': 5, 'hemisphere_id': 2, 'projection_density': 2.0, 'is_injection': False},
        
        # Exp 2 (Right Inj) -> Target in Left (Contra)
        {'experiment_id': 200, 'structure_id': 5, 'hemisphere_id': 1, 'projection_density': 4.0, 'is_injection': False},
        # Exp 2 (Right Inj) -> Target in Right (Ipsi)
        {'experiment_id': 200, 'structure_id': 5, 'hemisphere_id': 2, 'projection_density': 20.0, 'is_injection': False},
    ]
    unionizes_df = pd.DataFrame(unionizes_data)
    
    id_to_acronym = {5: 'MR'}
    
    # 2. Run Processing
    result_df = process_aggregation(
        unionizes=unionizes_df,
        experiments_df=experiments_df,
        id_to_acronym=id_to_acronym,
        metric='projection_density',
        agg_mode='mean',
        best_id=100
    )
    
    # 3. Verify
    # Extract the row for 'MR'
    row = result_df[result_df['acronym'] == 'MR'].iloc[0]
    
    # Check Ipsi: Mean(Exp1-Left=10, Exp2-Right=20) = 15.0
    assert row['value_ipsi'] == 15.0, f"Expected Ipsi 15.0, got {row['value_ipsi']}"
    
    # Check Contra: Mean(Exp1-Right=2, Exp2-Left=4) = 3.0
    assert row['value_contra'] == 3.0, f"Expected Contra 3.0, got {row['value_contra']}"
    
    # Check Left: Mean(Exp1-Left=10, Exp2-Left=4) = 7.0
    assert row['value_left'] == 7.0, f"Expected Left 7.0, got {row['value_left']}"
    
    # Check Right: Mean(Exp1-Right=2, Exp2-Right=20) = 11.0
    assert row['value_right'] == 11.0, f"Expected Right 11.0, got {row['value_right']}"
    
    # Check Mean: Mean(10, 2, 4, 20) = 36 / 4 = 9.0
    assert row['value_mean'] == 9.0, f"Expected Mean 9.0, got {row['value_mean']}"

    print("\n[SUCCESS] Aggregation Test Passed!")

if __name__ == "__main__":
    test_aggregation_mixed_experiments()
