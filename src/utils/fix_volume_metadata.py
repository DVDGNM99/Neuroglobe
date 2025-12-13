import sys
from pathlib import Path
from vedo import Volume

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.logger_config import log
from src.definitions import ATLAS_RESOLUTION

def fix_volume(path, target_spacing=ATLAS_RESOLUTION):
    log.info(f"--- Fixing Volume & Converting to Mesh: {path} ---")
    try:
        # 1. Load Data
        vol = Volume(path)
        log.info(f"Original Spacing: {vol.spacing()}")
        
        # 2. Force Metadata (Reconstruct to be safe like filter_tracts.py)
        data = vol.tonumpy()
        # Create new volume with explicit spacing/origin
        new_vol = Volume(data, spacing=target_spacing, origin=(0, 0, 0))
        
        log.info(f"New Spacing:      {new_vol.spacing()}")
        log.info(f"New Origin:       {new_vol.origin()}")
        
        # 3. Generate Isosurface (Mesh)
        # This aligns the workflow with 'Filtered' mode which works.
        dmax = new_vol.scalar_range()[1]
        threshold = dmax * 0.05
        log.info(f"Generating Isosurface (Threshold={threshold:.4f})...")
        
        mesh = new_vol.isosurface(value=threshold)
        
        # 4. Save as VTK
        output_path = path.replace(".nrrd", "_fixed.vtk")
        log.info(f"Saving Mesh to: {output_path}")
        mesh.write(output_path)
        log.info("Done.")
        return output_path
    except Exception as e:
        log.error(f"Error fixing volume: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log.error("Usage: python fix_volume_metadata.py <path_to_nrrd>")
    else:
        fix_volume(sys.argv[1])
