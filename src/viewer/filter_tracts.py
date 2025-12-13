import yaml
import numpy as np
from pathlib import Path
from brainglobe_atlasapi import BrainGlobeAtlas
from vedo import Volume

import yaml
import numpy as np
from pathlib import Path
from brainglobe_atlasapi import BrainGlobeAtlas
from vedo import Volume

from src.definitions import CONFIGS_DIR, TRACTS_DIR
from src.logger_config import log

# --- PATH CONFIGURATION ---
CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"
DATA_DIR = TRACTS_DIR
OUTPUT_NAME = "filtered_tracts.vtk"
ATLAS_NAME = "allen_mouse_25um"

def load_targets_from_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found at {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
        
    targets = cfg.get("selection", {}).get("custom_targets", [])
    clean_targets = [t.split("#")[0].strip() for t in targets]
    return clean_targets

def get_latest_tract_file():
    """Finds the most recent .nrrd file and returns the ABSOLUTE path."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Directory not found: {DATA_DIR}")
    
    files = list(DATA_DIR.glob("*.nrrd"))
    if not files:
        files = list(DATA_DIR.glob("*.mhd")) 
    
    if not files:
        raise FileNotFoundError("No tractography files found in data/processed/tracts")
    
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0].resolve()

def run_filter(input_path: Path = None, output_path: Path = None):
    log.info(f"--- FILTERING TRACTS (VOXEL MODE) ---")
    
    # 1. Load Targets
    try:
        target_regions = load_targets_from_config()
        log.info(f"Targets from Config: {target_regions}")
    except Exception as e:
        log.error(f"[ERROR] Config Error: {e}")
        return None

    if not target_regions:
        log.error("[ERROR] No targets found in mining_config.yaml.")
        return None

    # 2. Find Input File
    try:
        if input_path:
            input_file = input_path
        else:
            input_file = get_latest_tract_file()
        log.info(f"Input Absolute Path: {input_file}")
    except Exception as e:
        log.error(f"[ERROR] File Error: {e}")
        return None

    if output_path is None:
        output_path = DATA_DIR / OUTPUT_NAME
    
    # 3. Load Atlas
    log.info(f"Loading Atlas: {ATLAS_NAME}...")
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)
    
    # 4. Load Volume
    log.info(f"Loading Volume...")
    vol = Volume(str(input_file))
    vol_data = vol.tonumpy()
    
    log.info(f"Volume Shape: {vol_data.shape}")
    log.info(f"Atlas Shape: {bg_atlas.annotation.shape}")
    
    # Verify shapes match
    if vol_data.shape != bg_atlas.annotation.shape:
        log.warning(f"[WARN] Shape mismatch! Volume: {vol_data.shape}, Atlas: {bg_atlas.annotation.shape}")
        
        # Try to transpose
        if sorted(vol_data.shape) == sorted(bg_atlas.annotation.shape):
            log.info("[INFO] Dimensions are permuted. Attempting to auto-transpose...")
            
            target_shape = bg_atlas.annotation.shape
            current_shape = vol_data.shape
            
            perm = []
            used_indices = set()
            possible = True
            
            for dim in target_shape:
                found = False
                for i, cdim in enumerate(current_shape):
                    if cdim == dim and i not in used_indices:
                        perm.append(i)
                        used_indices.add(i)
                        found = True
                        break
                if not found:
                    possible = False
                    break
            
            if possible and len(perm) == 3:
                log.info(f"[INFO] Transposing with permutation: {perm}")
                vol_data = np.transpose(vol_data, axes=perm)
                log.info(f"[INFO] New Volume Shape: {vol_data.shape}")
            else:
                log.error("[ERROR] Could not determine permutation. Aborting.")
                return None
        else:
            log.error("[ERROR] Shapes are incompatible (not a permutation). Aborting.")
            return None

    # 5. Create Voxel Mask
    log.info("Generating Voxel Mask...")
    full_mask = np.zeros(bg_atlas.annotation.shape, dtype=bool)
    
    for region in target_regions:
        try:
            structure = bg_atlas.structures[region]
            sid = structure['id']
            mask = bg_atlas.get_structure_mask(sid)
            full_mask = np.logical_or(full_mask, mask)
        except KeyError:
            log.warning(f"[WARN] Region '{region}' not found in atlas.")
        except Exception as e:
            log.warning(f"[WARN] Error masking '{region}': {e}")

    # 6. Apply Mask
    log.info("Applying Mask to Volume...")
    vol_data[~full_mask] = 0
    
    # --- RE-ORIENT TO RAW SPACE ---
    if vol_data.shape == (528, 320, 456): # Atlas Shape
         log.info("[INFO] Re-transposing back to Raw Space [2, 1, 0]...")
         vol_data = np.transpose(vol_data, axes=[2, 1, 0])
         log.info(f"[INFO] Final Volume Shape: {vol_data.shape}")

    # Update volume data
    res = bg_atlas.resolution
    masked_vol = Volume(vol_data, spacing=res, origin=(0,0,0))
    
    # 7. Isosurface & Save
    log.info("Extracting Isosurface...")
    dmax = masked_vol.scalar_range()[1]
    threshold = dmax * 0.05 
    filtered_tracts = masked_vol.isosurface(value=threshold)
    
    log.info(f"Saving to {output_path}...")
    filtered_tracts.write(str(output_path))
    log.info(f"[SUCCESS] Done! File saved: {output_path.name}")
    return output_path

if __name__ == "__main__":
    run_filter()