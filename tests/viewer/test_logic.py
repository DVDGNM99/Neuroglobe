import pytest
import sys
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.viewer import logic

def test_hex_to_rgb():
    assert logic.hex_to_rgb("#FFFFFF") == [255, 255, 255]
    assert logic.hex_to_rgb("#000000") == [0, 0, 0]
    assert logic.hex_to_rgb("#FF0000") == [255, 0, 0]

def test_load_regions_config(tmp_path):
    # Create a dummy config file
    config_data = [
        {"acronym": "VISp", "name": "Primary visual area", "color_hex_triplet": "00FF00"}
    ]
    config_file = tmp_path / "regions.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
        
    # Test loading
    regions = logic.load_regions_config(str(config_file))
    assert len(regions) == 1
    assert regions[0].acronym == "VISp"
    assert regions[0].color == "#00FF00"

def test_process_csv_data(tmp_path):
    # Create a dummy CSV
    csv_content = "acronym,projection_density\nVISp,0.5\nMOs,0.8"
    csv_file = tmp_path / "data.csv"
    with open(csv_file, "w") as f:
        f.write(csv_content)
        
    # Test processing
    data = logic.process_csv_data(str(csv_file))
    assert len(data) == 2
    assert data[0]['acronym'] == 'MOs' # Sorted by density descending usually? 
    # Actually logic.process_csv_data sorts by density descending.
    assert data[0]['value'] == 0.8
