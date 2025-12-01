import shutil
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache
import yaml

# --- CONFIGURATION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "mining_config.yaml"
DATA_RAW_PATH = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_TRACTS = PROJECT_ROOT / "data" / "processed" / "tracts"

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
    print(f"[TRACTS] Processing Experiment {experiment_id}...")
    
    # Initialize Cache
    mcc = MouseConnectivityCache(manifest_file=str(DATA_RAW_PATH / "manifest.json"))
    
    DATA_PROCESSED_TRACTS.mkdir(parents=True, exist_ok=True)

    try:
        import SimpleITK as sitk
    except ImportError:
        print("[ERROR] SimpleITK not found. Please install it in 'allensdk' env.")
        return False

    success_count = 0

    # --- 1. PROJECTION DENSITY ---
    print(f"  > Fetching projection_density...")
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
        print(f"    [OK] Saved {dest_path.name}")
        success_count += 1
    except Exception as e:
        print(f"    [ERROR] Failed to fetch density: {e}")

    # --- 2. PROJECTION ENERGY ---
    print(f"  > Fetching projection_energy...")
    try:
        # Attempt to use internal API if public method doesn't exist
        # Note: This is a best-effort guess based on API structure
        dest_name = f"{experiment_id}_energy.mhd" # API usually downloads MHD
        dest_path = DATA_PROCESSED_TRACTS / dest_name
        
        # Check if we can download it directly via API
        # mcc.api is usually a GridDataApi
        if hasattr(mcc, 'api') and hasattr(mcc.api, 'download_projection_energy'):
            mcc.api.download_projection_energy(experiment_id, str(dest_path))
    seed = cfg["experiment"]["seed_acronym"]
    print(f"Finding experiments for seed: {seed}")
    
    exps, _ = get_experiments(seed, DATA_RAW_PATH)
    
    if not exps.empty:
        first_id = exps.iloc[0]['id']
        print(f"Testing download for Experiment ID: {first_id}")
        fetch_and_process_tracts(first_id)
    else:
        print("No experiments found to test.")