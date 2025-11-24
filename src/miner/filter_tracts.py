import numpy as np
from pathlib import Path
from brainglobe_atlasapi import BrainGlobeAtlas
from vedo import Volume, merge, Mesh

# --- CONFIGURAZIONE ---
ATLAS_NAME = "allen_mouse_25um"
INPUT_FILE = Path("../../data/processed/tracts/480074702.nrrd") # Verifica il nome file!
OUTPUT_FILE = Path("../../data/processed/tracts/filtered_PFC_aligned.vtk")

# Le tue coordinate di allineamento (Vengono applicate qui PERMANENTEMENTE)
SHIFT_X = 600    # + va dx, - va sx
SHIFT_Y = -100    # + va giù (Ventrale), - va su (Dorsale)
SHIFT_Z = -200   # + va dietro, - va avanti

# Lista aree PFC (Prefrontal Cortex)
PFC_REGIONS = ["PL", "ILA", "ORB", "ACAd", "ACAv", "MOs"]

def run_filter():
    print(f"--- FILTERING TRACTS (Target: {PFC_REGIONS}) ---")
    
    # 1. Carica Atlante
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)
    
    # 2. Crea la maschera 3D della PFC (unendo le regioni)
    print("Generating PFC Mask from Atlas...")
    pfc_meshes = []
    for region in PFC_REGIONS:
        try:
            # Ottieni la mesh della regione dall'atlante
            mesh_obj = bg_atlas.mesh_from_structure(region)
            # Converti in vedo Mesh
            vedo_mesh = Mesh(mesh_obj)
            pfc_meshes.append(vedo_mesh)
        except:
            print(f"Skipping region {region} (not found)")
            
    if not pfc_meshes:
        print("Error: No regions found.")
        return

    # Unisci tutte le mesh PFC in una sola forma complessa
    pfc_mask_mesh = merge(pfc_meshes)
    print(f"PFC Mask created (merged {len(pfc_meshes)} regions).")

    # 3. Carica la Trattografia
    print(f"Loading raw volume: {INPUT_FILE}")
    vol = Volume(str(INPUT_FILE))
    
    # 4. APPLICA L'ALLINEAMENTO ORA (Permanente)
    # Applichiamo la stessa logica di rendering.py
    center = vol.center_of_mass()
    # Rotazione Y 270
    vol.rotate(270, axis=(0,1,0), point=center)
    # Shift
    vol.shift(SHIFT_X, SHIFT_Y, SHIFT_Z)
    print("Alignment (Rotation + Shift) applied to volume.")

    # 5. FILTRAGGIO (Cut)
    # Usiamo "cut_with_mesh" per tenere solo ciò che è DENTRO la PFC
    print("Filtering volume with PFC mask (this takes time)...")
    # isosurface per convertire in mesh modificabile
    threshold = vol.scalar_range()[1] * 0.10
    vol_mesh = vol.isosurface(value=threshold)
    
    # Taglia: invert=True significa "tieni quello dentro la maschera"
    filtered_tracts = vol_mesh.cut_with_mesh(pfc_mask_mesh, invert=True)
    
    # 6. Salva
    print(f"Saving to {OUTPUT_FILE}...")
    filtered_tracts.write(str(OUTPUT_FILE))
    print("Done! Now load this file in rendering.py without applying shifts.")

if __name__ == "__main__":
    run_filter()