import shutil
from pathlib import Path

from neuroglobe.projections.config import load_mining_config
from neuroglobe.projections.definitions import (
    ATLAS_RESOLUTION,
    RAW_DATA_DIR,
    TRACTS_DIR,
    CONFIGS_DIR,
)
from neuroglobe.projections.logger_config import log

# --- CONFIGURATION ---
# --- CONFIGURATION ---
CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"
DATA_RAW_PATH = RAW_DATA_DIR
DATA_PROCESSED_TRACTS = TRACTS_DIR

def load_config():
    return load_mining_config(CONFIG_PATH)


def _spacing_tuple(value) -> tuple[float, float, float]:
    if isinstance(value, (int, float)):
        return (float(value),) * 3
    values = tuple(float(item) for item in value)
    if len(values) != 3:
        raise ValueError(f"Expected three spacing values, got {values!r}")
    return values


def _write_density_with_geometry(data, metadata, source_path: Path, destination: Path) -> None:
    """Preserve the Allen NRRD byte-for-byte when the cache file is available."""

    if source_path.exists():
        shutil.copy2(source_path, destination)
        return

    import SimpleITK as sitk

    # Allen arrays are AP/DV/ML. SimpleITK arrays are supplied as Z/Y/X, so
    # transpose explicitly to retain the physical AP/DV/ML image size.
    array_zyx = data.transpose(2, 1, 0)
    image = sitk.GetImageFromArray(array_zyx)
    image.SetSpacing(
        _spacing_tuple(metadata.get("resolution", ATLAS_RESOLUTION))
    )
    origin = metadata.get("space origin", metadata.get("origin", (0, 0, 0)))
    image.SetOrigin(tuple(float(value) for value in origin))
    sitk.WriteImage(image, str(destination), useCompression=True)

def fetch_and_process_tracts(experiment_id):
    """
    Downloads Projection Density AND Projection Energy for the given experiment ID.
    Saves them as:
      - {id}_density.nrrd
      - {id}_energy.nrrd
    """
    log.info(f"[TRACTS] Processing Experiment {experiment_id}...")
    
    from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

    # Initialize Cache
    mcc = MouseConnectivityCache(
        manifest_file=str(DATA_RAW_PATH / "manifest.json"), resolution=25
    )
    
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
        
        source_path = (
            DATA_RAW_PATH
            / f"experiment_{experiment_id}"
            / "projection_density_25.nrrd"
        )
        _write_density_with_geometry(data, meta, source_path, dest_path)
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

def main() -> int:
    from neuroglobe.projections.miner.fetch import get_experiments

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
        if not fetch_and_process_tracts(best_id):
            return 1
        log.info("[SUCCESS] Tract extraction complete.")
    else:
        log.error("[ERROR] No experiments found for seed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
