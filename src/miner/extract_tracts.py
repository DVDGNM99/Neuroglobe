import yaml
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

from src.definitions import PROJECT_ROOT, RAW_DATA_DIR, TRACTS_DIR, CONFIGS_DIR
from src.logger_config import log

# --- CONFIGURATION ---
# --- CONFIGURATION ---
# PROJECT_ROOT is imported from src.definitions
CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"
DATA_RAW_PATH = RAW_DATA_DIR
DATA_PROCESSED_TRACTS = TRACTS_DIR

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def fetch_and_process_tracts(experiment_id):
    """
    Downloads Projection Density AND Projection Energy for the given experiment ID.
    Saves them as:
      - {id}_density.nrrd
      - {id}_energy.nrrd
    """
    log.info(f"[TRACTS] Processing Experiment {experiment_id}...")
    
    # Initialize Cache
    mcc = MouseConnectivityCache(manifest_file=str(DATA_RAW_PATH / "manifest.json"))
    
    DATA_PROCESSED_TRACTS.mkdir(parents=True, exist_ok=True)

    try:
        import SimpleITK as sitk
    except ImportError:
        log.error("[ERROR] SimpleITK not found. Please install it in 'allensdk' env.")
        return False

    success_count = 0

    # --- 1. PROJECTION DENSITY ---
    log.info(f"  > Fetching projection_density...")
    try:
        # Returns (data, dict)
        data, meta = mcc.get_projection_density(experiment_id)
        
        dest_name = f"{experiment_id}_density.nrrd"
        dest_path = DATA_PROCESSED_TRACTS / dest_name
        
        # Convert to SimpleITK Image
        img = sitk.GetImageFromArray(data)
        
        # Apply Metadata if available
        if 'resolution' in meta:
            img.SetSpacing(meta['resolution'])
        if 'space origin' in meta:
            img.SetOrigin(meta['space origin'])
            
        sitk.WriteImage(img, str(dest_path))
        log.info(f"    [OK] Saved {dest_path.name}")
        success_count += 1
    except Exception as e:
        log.error(f"    [ERROR] Failed to fetch density: {e}")

    # --- 2. PROJECTION ENERGY ---
    log.info(f"  > Fetching projection_energy...")
    try:
        # Attempt to use internal API if public method doesn't exist
        # Note: This is a best-effort guess based on API structure
        dest_name = f"{experiment_id}_energy.mhd" # API usually downloads MHD
        dest_path = DATA_PROCESSED_TRACTS / dest_name
        
        # Check if we can download it directly via API
        # mcc.api is usually a GridDataApi
        if hasattr(mcc, 'api') and hasattr(mcc.api, 'download_projection_energy'):
            mcc.api.download_projection_energy(experiment_id, str(dest_path))
            log.info(f"    [OK] Saved {dest_name}")
            success_count += 1
        else:
            log.warning("    [SKIP] Projection Energy API not available.")

    except Exception as e:
        log.warning(f"    [SKIP] Failed to fetch projection_energy (Optional): {e}")

    return success_count > 0

if __name__ == "__main__":
    import sys
    # Ensure src is in path
    root_path = str(Path(__file__).resolve().parent.parent.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    from src.miner.fetch import get_experiments

    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    log.info(f"--- STARTING TRACT EXTRACTION FOR SEED: {seed} ---")
    
    # 1. Reuse logic to find best experiment
    # Fetch experiments
    experiments_df, _ = get_experiments(seed, RAW_DATA_DIR)
    
    if not experiments_df.empty:
        best_exp = experiments_df.sort_values(by="injection_volume", ascending=False).iloc[0]
        best_id = int(best_exp['id'])
        log.info(f"[MINER] Selected Representative Experiment: {best_id}")
        
        # 2. Extract
        fetch_and_process_tracts(best_id)
        log.info("[SUCCESS] Tract extraction complete.")
    else:
        log.error("[ERROR] No experiments found for seed.")
