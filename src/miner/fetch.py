import sys
import yaml
import pandas as pd
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache



from src.definitions import CONFIGS_DIR, RAW_DATA_DIR
from src.logger_config import log

# --- Path Configuration ---
CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def get_experiments(seed_acronym: str, manifest_path: Path):
    """
    Queries the Allen API to find experiments with injection in the seed_acronym.
    """
    log.info(f"Initializing MouseConnectivityCache at: {manifest_path}")
    
    # The manifest file manages the downloaded data. 
    # resolution=25 matches the CCF version we use in BrainGlobe.
    mcc = MouseConnectivityCache(manifest_file=str(manifest_path / "manifest.json"),
                                 resolution=25)
    
    ontology = mcc.get_structure_tree()
    
    # 1. Get numeric ID of the seed region
    try:
        seed_structure = ontology.get_structures_by_acronym([seed_acronym])[0]
        seed_id = seed_structure['id']
        log.info(f"Target Seed: {seed_acronym} (ID: {seed_id})")
    except IndexError:
        raise ValueError(f"Region '{seed_acronym}' not found in Allen Ontology.")

    # 2. Find experiments
    log.info("Querying experiments... (this might take a moment)")
    experiments = mcc.get_experiments(dataframe=True, 
                                      injection_structure_ids=[seed_id])
    
    log.info(f"Found {len(experiments)} experiments injected in {seed_acronym}")
    return experiments, mcc

if __name__ == "__main__":
    # 1. Load Config
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    # 2. Ensure raw folder exists
    DATA_RAW_PATH.mkdir(parents=True, exist_ok=True)
    
    # 3. Fetch
    experiments_df, mcc_instance = get_experiments(seed, RAW_DATA_DIR)
    
    # 4. Preview
    log.info("\n--- Experiment Preview ---")
    log.info(experiments_df[["id", "gender", "strain", "injection_volume"]].head())