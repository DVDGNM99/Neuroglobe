import yaml
import shutil
import os
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# --- Configurazione Percorsi ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "mining_config.yaml"
DATA_RAW_PATH = BASE_DIR / "data" / "raw"
DATA_PROCESSED_TRACTS = BASE_DIR / "data" / "processed" / "tracts"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("Config file missing!")
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def fetch_and_process_tracts(experiment_id: int):
    print(f"[TRACTS] Processing Experiment {experiment_id}...")
    
    mcc = MouseConnectivityCache(manifest_file=str(DATA_RAW_PATH / "manifest.json"),
                                 resolution=25)
    
    # 1. Trigger Download
    print(f"[TRACTS] Triggering download via SDK...")
    try:
        mcc.get_projection_density(experiment_id)
    except Exception as e:
        print(f"[ERROR] Download trigger failed: {e}")
        return False

    # 2. Ricerca File (NRRD o MHD)
    experiment_dir = DATA_RAW_PATH / f"experiment_{experiment_id}"
    
    if not experiment_dir.exists():
        print(f"[ERROR] Cache folder not found: {experiment_dir}")
        return False
        
    # Cerchiamo prima il formato moderno (.nrrd)
    nrrd_files = list(experiment_dir.glob("*.nrrd"))
    mhd_files = list(experiment_dir.glob("*.mhd"))
    
    DATA_PROCESSED_TRACTS.mkdir(parents=True, exist_ok=True)

    # --- CASO A: Formato Moderno (.nrrd) ---
    if nrrd_files:
        source_path = nrrd_files[0]
        dest_name = f"{experiment_id}.nrrd"
        dest_path = DATA_PROCESSED_TRACTS / dest_name
        
        print(f"[TRACTS] Found NRRD format: {source_path.name}")
        try:
            shutil.copy(source_path, dest_path)
            print(f"[SUCCESS] Tractography (NRRD) ready: {dest_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Copy failed: {e}")
            return False

    # --- CASO B: Formato Vecchio (.mhd + .raw) ---
    elif mhd_files:
        source_mhd = mhd_files[0]
        source_raw = source_mhd.with_suffix('.raw')
        
        dest_mhd = DATA_PROCESSED_TRACTS / f"{experiment_id}.mhd"
        dest_raw = DATA_PROCESSED_TRACTS / f"{experiment_id}.raw"
        
        print(f"[TRACTS] Found MHD format: {source_mhd.name}")
        
        try:
            shutil.copy(source_raw, dest_raw)
            # Patch header
            with open(source_mhd, 'r') as f: lines = f.readlines()
            with open(dest_mhd, 'w') as f:
                for line in lines:
                    if line.strip().startswith("ElementDataFile"):
                        f.write(f"ElementDataFile = {experiment_id}.raw\n")
                    else:
                        f.write(line)
            print(f"[SUCCESS] Tractography (MHD) ready: {dest_mhd}")
            return True
        except Exception as e:
            print(f"[ERROR] MHD processing failed: {e}")
            return False
            
    else:
        print(f"[ERROR] No valid density files (.nrrd or .mhd) found in {experiment_dir}")
        return False

if __name__ == "__main__":
    print("--- Tractography Extractor Test (Dual Format Support) ---")
    from fetch import get_experiments
    
    cfg = load_config()
    seed = cfg["experiment"]["seed_acronym"]
    print(f"Finding experiments for seed: {seed}")
    
    exps, _ = get_experiments(seed, DATA_RAW_PATH)
    
    if not exps.empty:
        first_id = exps.iloc[0]['id']
        print(f"Testing download for Experiment ID: {first_id}")
        fetch_and_process_tracts(first_id)
    else:
        print("No experiments found to test.")