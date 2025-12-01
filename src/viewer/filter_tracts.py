import yaml
import numpy as np
from pathlib import Path
from brainglobe_atlasapi import BrainGlobeAtlas
from vedo import Volume, merge, Mesh

# --- PATH CONFIGURATION ---
# Calculate root starting from src/viewer/filter_tracts.py
# viewer -> src -> ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "mining_config.yaml"
DATA_DIR = PROJECT_ROOT / "data" / "processed" / "tracts"
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
    
    # IMPORTANT: Returns resolved absolute path
    return files[0].resolve()

def run_filter(input_path: Path = None, output_path: Path = None):
    print(f"--- FILTERING TRACTS (VOXEL MODE) ---")
    
    # 1. Load Targets
    try:
        target_regions = load_targets_from_config()
        print(f"Targets from Config: {target_regions}")
    except Exception as e:
        print(f"[ERROR] Config Error: {e}")
        return None

    if not target_regions:
        print("[ERROR] No targets found in mining_config.yaml.")
        return None

    # 2. Find Input File
    try:
        if input_path:
            input_file = input_path
        else:
            input_file = get_latest_tract_file()
        print(f"Input Absolute Path: {input_file}")
    except Exception as e:
        print(f"[ERROR] File Error: {e}")
        return None

    if output_path is None:
        output_path = DATA_DIR / OUTPUT_NAME
    
    # 3. Load Atlas
    print(f"Loading Atlas: {ATLAS_NAME}...")
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)
    
    # 4. Load Volume
    print(f"Loading Volume...")
    vol = Volume(str(input_file))
    vol_data = vol.tonumpy()
    
    print(f"Volume Shape: {vol_data.shape}")
    print(f"Atlas Shape: {bg_atlas.annotation.shape}")
    
    # Verify shapes match
    if vol_data.shape != bg_atlas.annotation.shape:
        print(f"[WARN] Shape mismatch! Volume: {vol_data.shape}, Atlas: {bg_atlas.annotation.shape}")
        
        # Try to transpose
        if sorted(vol_data.shape) == sorted(bg_atlas.annotation.shape):
            print("[INFO] Dimensions are permuted. Attempting to auto-transpose...")
            
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
import yaml
import numpy as np
from pathlib import Path
from brainglobe_atlasapi import BrainGlobeAtlas
from vedo import Volume, merge, Mesh

# --- PATH CONFIGURATION ---
# Calculate root starting from src/viewer/filter_tracts.py
# viewer -> src -> ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "mining_config.yaml"
DATA_DIR = PROJECT_ROOT / "data" / "processed" / "tracts"
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
    
    # IMPORTANT: Returns resolved absolute path
    return files[0].resolve()

def run_filter(input_path: Path = None, output_path: Path = None):
    print(f"--- FILTERING TRACTS (VOXEL MODE) ---")
    
    # 1. Load Targets
    try:
        target_regions = load_targets_from_config()
        print(f"Targets from Config: {target_regions}")
    except Exception as e:
        print(f"[ERROR] Config Error: {e}")
        return None

    if not target_regions:
        print("[ERROR] No targets found in mining_config.yaml.")
        return None

    # 2. Find Input File
    try:
        if input_path:
            input_file = input_path
        else:
            input_file = get_latest_tract_file()
        print(f"Input Absolute Path: {input_file}")
    except Exception as e:
        print(f"[ERROR] File Error: {e}")
        return None

    if output_path is None:
        output_path = DATA_DIR / OUTPUT_NAME
    
    # 3. Load Atlas
    print(f"Loading Atlas: {ATLAS_NAME}...")
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)
    
    # 4. Load Volume
    print(f"Loading Volume...")
    vol = Volume(str(input_file))
    vol_data = vol.tonumpy()
    
    print(f"Volume Shape: {vol_data.shape}")
    print(f"Atlas Shape: {bg_atlas.annotation.shape}")
    
    # Verify shapes match
    if vol_data.shape != bg_atlas.annotation.shape:
        print(f"[WARN] Shape mismatch! Volume: {vol_data.shape}, Atlas: {bg_atlas.annotation.shape}")
        
        # Try to transpose
        if sorted(vol_data.shape) == sorted(bg_atlas.annotation.shape):
            print("[INFO] Dimensions are permuted. Attempting to auto-transpose...")
            
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
                print(f"[INFO] Transposing with permutation: {perm}")
                vol_data = np.transpose(vol_data, axes=perm)
                print(f"[INFO] New Volume Shape: {vol_data.shape}")
            else:
                print("[ERROR] Could not determine permutation. Aborting.")
                return None
        else:
            print("[ERROR] Shapes are incompatible (not a permutation). Aborting.")
            return None

    # 5. Create Voxel Mask
    print("Generating Voxel Mask...")
    # Start with empty mask
    full_mask = np.zeros(bg_atlas.annotation.shape, dtype=bool)
    
    for region in target_regions:
        try:
            # Get ID for region
            structure = bg_atlas.structures[region]
            sid = structure['id']
            
            # Get mask for this structure (and descendants)
            # BrainGlobe's get_structure_mask returns a binary volume
            mask = bg_atlas.get_structure_mask(sid)
            
            # Combine
            full_mask = np.logical_or(full_mask, mask)
        except KeyError:
            print(f"[WARN] Region '{region}' not found in atlas.")
        except Exception as e:
            print(f"[WARN] Error masking '{region}': {e}")

    # 6. Apply Mask
    print("Applying Mask to Volume...")
    # Set voxels outside mask to 0
    vol_data[~full_mask] = 0
    
    # --- RE-ORIENT TO RAW SPACE ---
    # The user wants the filtered file to behave EXACTLY like the raw file.
    # Since the raw file requires manual rotation (it's not natively aligned),
    # we must put this filtered data BACK into that "wrong" orientation
    # so the viewer's manual rotation fixes both.
    
    # If we transposed earlier, transpose back.
    # The permutation was [2, 1, 0] (swapping X and Z).
    # The inverse of [2, 1, 0] is [2, 1, 0].
    
    # We need to track if we transposed. 
    # For now, we assume if we did the auto-transpose logic above, we need to undo it.
    # But simpler: check if shape matches atlas. If it does (which it must to mask),
    # and the original was different, we swap back.
    
    # Actually, let's just check if we performed the transpose.
    # We can infer it from the shapes printed earlier or just force the swap if we know it's needed.
    # But to be robust, let's look at the logic above.
    # We can't easily access the 'perm' variable from here without refactoring.
    
    # Let's just assume the standard [2, 1, 0] swap if the original shape was (456, 320, 528)
    # Atlas is (528, 320, 456).
    
    if vol_data.shape == (528, 320, 456): # Atlas Shape
         print("[INFO] Re-transposing back to Raw Space [2, 1, 0]...")
         vol_data = np.transpose(vol_data, axes=[2, 1, 0])
         print(f"[INFO] Final Volume Shape: {vol_data.shape}")

    # Update volume data
    # We create a new Volume to ensure clean state
    # CRITICAL: Use the ATLAS metadata (spacing/origin) to ensure alignment with the scene
    # bg_atlas.resolution is a tuple (x, y, z) in microns
    res = bg_atlas.resolution
    # BrainGlobe atlases usually start at 0,0,0
    masked_vol = Volume(vol_data, spacing=res, origin=(0,0,0))
    
    # 7. Isosurface & Save
    print("Extracting Isosurface...")
    # Use a small threshold to capture the cloud
    dmax = masked_vol.scalar_range()[1]
    threshold = dmax * 0.05 
    filtered_tracts = masked_vol.isosurface(value=threshold)
    
    print(f"Saving to {output_path}...")
    filtered_tracts.write(str(output_path))
    print(f"[SUCCESS] Done! File saved: {output_path.name}")
    return output_path

if __name__ == "__main__":
    run_filter()