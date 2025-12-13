import pytest
import json


from src.viewer import logic

def test_hex_to_rgb():
    assert logic.hex_to_rgb("#FFFFFF") == [255, 255, 255]
    assert logic.hex_to_rgb("#000000") == [0, 0, 0]
    assert logic.hex_to_rgb("#FF0000") == [255, 0, 0]

def test_load_regions_config(tmp_path):
    # Create a dummy config file
    # Updated to match dict structure logic.py expects:
    # { "acronym": "Name" }
    config_data = {
        "VISp": "Primary visual area",
        "MOs": "Secondary motor area"
    }
    config_file = tmp_path / "regions.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f)
        
    # Test loading
    regions = logic.load_regions_config(str(config_file))
    # logic.load_regions_config returns a list of RegionItem objects
    assert len(regions) == 2
    visp = next(r for r in regions if r.acronym == "VISp")
    assert visp.name == "Primary visual area"

def test_process_csv_data(tmp_path):
    # Create a dummy CSV
    csv_content = "acronym,value\nVISp,0.5\nMOs,0.8"
    csv_file = tmp_path / "data.csv"
    with open(csv_file, "w") as f:
        f.write(csv_content)
        
    # Test processing
    data, _, _ = logic.process_csv_data(str(csv_file))
    assert len(data) == 2
    # CSV order is preserved for non-seeds
    assert data[0]['acronym'] == 'VISp' 
    
    assert data[1]['acronym'] == 'MOs'
