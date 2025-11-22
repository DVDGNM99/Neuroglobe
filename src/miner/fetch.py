import yaml
import pandas as pd
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# --- Configurazione Percorsi ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "mining_config.yaml"
DATA_RAW_PATH = PROJECT_ROOT / "data" / "raw"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def get_experiments(seed_acronym: str, manifest_path: Path):
    """
    Interroga l'Allen API per trovare esperimenti con iniezione nel seed_acronym.
    """
    print(f"Initializing MouseConnectivityCache at: {manifest_path}")
    
    # The manifest file manages the downloaded data. 
    # resolution=25 matches the CCF version we use in BrainGlobe.
    mcc = MouseConnectivityCache(manifest_file=str(manifest_path / "manifest.json"),
                                 resolution=25)
    
    ontology = mcc.get_structure_tree()
    
    # 1. Ottieni ID numerico della regione seed
    try:
        seed_structure = ontology.get_structures_by_acronym([seed_acronym])[0]
        seed_id = seed_structure['id']
        print(f"Target Seed: {seed_acronym} (ID: {seed_id})")
    except IndexError:
        raise ValueError(f"Region '{seed_acronym}' not found in Allen Ontology.")

    # 2. Trova esperimenti
    print("Querying experiments... (this might take a moment)")
    experiments = mcc.get_experiments(dataframe=True, 
                                      injection_structure_ids=[seed_id])
    
    print(f"Found {len(experiments)} experiments injected in {seed_acronym}")
    return experiments, mcc

if __name__ == "__main__":
    # 1. Load Config
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    # 2. Ensure raw folder exists
    DATA_RAW_PATH.mkdir(parents=True, exist_ok=True)
    
    # 3. Fetch
    experiments_df, mcc_instance = get_experiments(seed, DATA_RAW_PATH)
    
    # 4. Preview
    print("\n--- Experiment Preview ---")
    print(experiments_df[["id", "gender", "strain", "injection_volume"]].head())