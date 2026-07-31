import unittest
import yaml
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Mock paths for testing
TEST_CONFIG_PATH = PROJECT_ROOT / "tests" / "test_config.yaml"
TEST_REGIONS_PATH = PROJECT_ROOT / "tests" / "test_regions.json"

class TestGUILogic(unittest.TestCase):

    def setUp(self):
        # Create dummy config
        self.config_data = {
            "experiment": {"seed_acronym": "TEST"},
            "selection": {"custom_targets": ["A", "B"], "use_custom_targets": True},
            "processing": {"metric": "projection_density"}
        }
        with open(TEST_CONFIG_PATH, 'w') as f:
            yaml.dump(self.config_data, f)

        # Create dummy regions
        self.regions_data = [
            {"acronym": "A", "name": "Region A"},
            {"acronym": "B", "name": "Region B"},
            {"acronym": "C", "name": "Region C"}
        ]
        with open(TEST_REGIONS_PATH, 'w') as f:
            json.dump(self.regions_data, f)

    def tearDown(self):
        # Cleanup
        if TEST_CONFIG_PATH.exists():
            TEST_CONFIG_PATH.unlink()
        if TEST_REGIONS_PATH.exists():
            TEST_REGIONS_PATH.unlink()

    def test_load_yaml(self):
        # Test loading the mock config
        with open(TEST_CONFIG_PATH, 'r') as f:
            loaded = yaml.safe_load(f)
        self.assertEqual(loaded["experiment"]["seed_acronym"], "TEST")

    def test_load_regions_logic(self):
        # simulate the logic in miner_gui.load_regions
        with open(TEST_REGIONS_PATH, 'r') as f:
            data = json.load(f)
            acronyms = [r['acronym'] for r in data if 'acronym' in r]
            sorted_acronyms = sorted(acronyms)
        
        self.assertEqual(sorted_acronyms, ["A", "B", "C"])

    def test_save_config_logic(self):
        # simulate saving logic
        new_seed = "NEW_SEED"
        self.config_data["experiment"]["seed_acronym"] = new_seed
        
        with open(TEST_CONFIG_PATH, 'w') as f:
            yaml.dump(self.config_data, f)
            
        # Verify
        with open(TEST_CONFIG_PATH, 'r') as f:
            reloaded = yaml.safe_load(f)
        
        self.assertEqual(reloaded["experiment"]["seed_acronym"], "NEW_SEED")

if __name__ == '__main__':
    unittest.main()
