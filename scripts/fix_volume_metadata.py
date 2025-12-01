import sys
from vedo import Volume

def fix_volume(path, target_spacing=(25, 25, 25)):
    print(f"--- Fixing Volume & Converting to Mesh: {path} ---")
    try:
        # 1. Load Data
        vol = Volume(path)
        print(f"Original Spacing: {vol.spacing()}")
        
        # 2. Force Metadata (Reconstruct to be safe like filter_tracts.py)
        data = vol.tonumpy()
        # Create new volume with explicit spacing/origin
        new_vol = Volume(data, spacing=target_spacing, origin=(0, 0, 0))
        
        print(f"New Spacing:      {new_vol.spacing()}")
        print(f"New Origin:       {new_vol.origin()}")
        
        # 3. Generate Isosurface (Mesh)
        # This aligns the workflow with 'Filtered' mode which works.
        dmax = new_vol.scalar_range()[1]
        threshold = dmax * 0.05
        print(f"Generating Isosurface (Threshold={threshold:.4f})...")
        
        mesh = new_vol.isosurface(value=threshold)
        
        # 4. Save as VTK
        output_path = path.replace(".nrrd", "_fixed.vtk")
        print(f"Saving Mesh to: {output_path}")
        mesh.write(output_path)
        print("Done.")
        return output_path
    except Exception as e:
        print(f"Error fixing volume: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_volume_metadata.py <path_to_nrrd>")
    else:
        fix_volume(sys.argv[1])
