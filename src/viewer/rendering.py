import traceback
import yaml
import numpy as np
from pathlib import Path
from datetime import datetime
from brainglobe_atlasapi import BrainGlobeAtlas
from brainrender import Scene, settings, actors
from vedo import Text2D, Sphere, Volume

# --- AESTHETIC CONFIGURATION ---
settings.SHOW_AXES = False
settings.WHOLE_SCREEN = False
settings.BACKGROUND_COLOR = "white"
settings.SCREENSHOT_TRANSPARENT_BACKGROUND = True

# --- ALIGNMENT CONFIGURATION ---
# Native alignment assumes data is registered to the atlas.
# Only rotation is kept for dataset-specific orientation fix.
ROTATION_MODE = "final_y_270"

# --- MANUAL FINE TUNING ---
# Small corrections if the native registration is slightly off.
SHIFT_X = 0      # + Right, - Left
SHIFT_Y = 0      # + Down (Ventral), - Up (Dorsal)
SHIFT_Z = 0      # + Back (Caudal), - Front (Rostral)

ROTATE_X = 0
ROTATE_Y = 90
ROTATE_Z = 0

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        print(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.default_scenes_dir = self.root_dir / "scenes"

    def render_scene(self, region_config: list, tract_file: Path = None, alpha=0.5, output_dir: Path = None, metadata: dict = None, visualization_mode="density"):
        scene = Scene(atlas_name=self.atlas_name, title="")
        
        # --- 0. CONTEXT (ROOT) ---
        self.root_actor = None
        try:
            print("[DEBUG] Attempting to add 'root' region...")
            # Try standard method
            self.root_actor = scene.add_brain_region("root", alpha=0.05, color="grey")
            if self.root_actor is None:
                 print("[WARN] add_brain_region('root') returned None. Trying scene.root...")
                 pass
            else:
                print("[DEBUG] Root actor created successfully.")
                self.root_actor.wireframe()
                
        except Exception as e: 
            print(f"[WARN] Root load issue: {e}")

        # --- 1. Target Regions ---
        print(f"Building scene with {len(region_config)} regions...")
        for item in region_config:
            try:
                # Add region and capture the actor
                reg_actor = scene.add_brain_region(item['acronym'], alpha=alpha, color=item['color'])
                if reg_actor:
                    # FORCE the name to be the acronym so picking works
                    reg_actor.name = item['acronym']
            except: pass

        # --- 2. Tractography / Streamlines ---
        if tract_file and tract_file.exists():
            print(f"[RENDER] Loading: {tract_file.name} (Mode: {visualization_mode})")
            try:
                tract_actor = None
                
                # CASE A: Pre-filtered Mesh (.vtk)
                if tract_file.suffix == ".vtk":
                    from vedo import load
                    tract_actor = load(str(tract_file))
                    if tract_actor:
                        # User requested NO heatmap on density, just solid color.
                        # Using a medium gray as requested
                        tract_actor.c("gray").alpha(0.5)
                        tract_actor.name = "Tractography (Filtered)" # Name it!
                        print("[RENDER] Loaded mesh directly.")

                # CASE B: Streamlines JSON (.json)
                elif tract_file.suffix == ".json" and "Streamlines" in visualization_mode:
                    from brainrender.actors import Streamlines
                    print(f"[RENDER] Loading Streamlines from {tract_file.name}")
                    # Brainrender Streamlines actor can load from file path
                    tract_actor = Streamlines(str(tract_file))
                    tract_actor.alpha(0.6)
                    tract_actor.name = "Streamlines"
                    
                # CASE C: Raw Volume (.nrrd)
                else:
                    print(f"[DEBUG] Attempting to load Volume: {tract_file}")
                    vol = Volume(str(tract_file))
                    dmin, dmax = vol.scalar_range()
                    print(f"[RENDER] Volume Range: {dmin:.4f} - {dmax:.4f}")
                    
                    if dmax > 0:
                        # Thresholding logic
                        # visualization_mode is now "Density (Raw)" or "Density (Filtered)"
                        threshold_val = dmax * 0.10 # Default 10%
                        
                        if "Raw" in visualization_mode:
                            threshold_val = dmax * 0.05 # Lower threshold for raw to ensure visibility
                        elif "Filtered" in visualization_mode:
                            threshold_val = dmax * 0.05
                            
                        print(f"[DEBUG] Thresholding at {threshold_val:.4f} (Mode: {visualization_mode})")

                        tract_actor = vol.isosurface(value=threshold_val)
                        
                        # Apply Viridis Colormap
                        tract_actor.cmap("viridis", vmin=threshold_val, vmax=dmax)
                        tract_actor.alpha(0.6)
                        tract_actor.name = "Tractography (Density)"
                        
                        # Add Scalar Bar (Legend) - DISABLED FOR DEBUGGING
                        # tract_actor.add_scalarbar(
                        #     title="Projection Density\n(Avg Fraction)",
                        #     pos=(0.05, 0.05), # Bottom Left
                        #     nlabels=5
                        # )
                    else:
                        print("[WARNING] Volume is empty (dmax=0).")

                # Apply Transformations
                if tract_actor:
                    # --- NATIVE ALIGNMENT ---
                    # The input file is expected to be correctly registered (spacing/origin).
                    
                    # Define a FIXED pivot point for rotations.
                    # CRITICAL: We use the Center of Mass of the RAW data as the pivot.
                    # This ensures that:
                    # 1. The Raw cloud rotates around itself (preserving the user's manual alignment).
                    # 2. The Filtered cloud rotates around the BRAIN CENTER (not its own center), keeping it aligned.
                    # CoM extracted from logs: [5778, 4066, 5975]
                    pivot_point = [5778, 4066, 5975]

                    # Legacy Rotation (Disabled)
                    if ROTATION_MODE == "final_y_270":
                        tract_actor.rotate(270, axis=(0,1,0), point=pivot_point)
                    
                    # Apply Manual Rotations (Fine Tuning)
                    if ROTATE_X != 0 or ROTATE_Y != 0 or ROTATE_Z != 0:
                        # center = tract_actor.center_of_mass() # OLD: caused misalignment for partial clouds
                        print(f"[ALIGN] Applying Manual Rotation: X={ROTATE_X}, Y={ROTATE_Y}, Z={ROTATE_Z}")
                        print(f"[ALIGN] Pivot Point: {pivot_point}")
                        
                        if ROTATE_X != 0: tract_actor.rotate(ROTATE_X, axis=(1,0,0), point=pivot_point)
                        if ROTATE_Y != 0: tract_actor.rotate(ROTATE_Y, axis=(0,1,0), point=pivot_point)
                        if ROTATE_Z != 0: tract_actor.rotate(ROTATE_Z, axis=(0,0,1), point=pivot_point)

                    # Apply Manual Fine Tuning
                    print(f"[ALIGN] Applying Manual Shift: {SHIFT_X}, {SHIFT_Y}, {SHIFT_Z}")
                    
                    com_before = tract_actor.center_of_mass()
                    print(f"[DEBUG] CoM Before: {com_before}")
                    
                    tract_actor.shift(SHIFT_X, SHIFT_Y, SHIFT_Z)
                    
                    com_after = tract_actor.center_of_mass()
                    print(f"[DEBUG] CoM After:  {com_after}")
                    
                    # Sanity check: Did it move?
                    diff = np.array(com_after) - np.array(com_before)
                    print(f"[DEBUG] Actual Movement: {diff}")
                        
                scene.add(tract_actor)

            except Exception as e:
                print(f"[ERROR] Tract render failed: {e}")
                traceback.print_exc()

        # --- 3. HUD & LEGEND ---
        hud = Text2D("S: Save | K: Style | X/Y/Z: Views", pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)

        # Add Region Scalar Bar (Separate Window)
        if metadata and "scalar_min" in metadata and "scalar_max" in metadata:
            try:
                s_min = metadata["scalar_min"]
                s_max = metadata["scalar_max"]
                
                print(f"[RENDER] Launching Legend Window: {s_min:.4f} - {s_max:.4f}")
                
                import subprocess
                import sys
                
                legend_script = self.root_dir / "src" / "viewer" / "show_legend.py"
                subprocess.Popen([sys.executable, str(legend_script), "--min", str(s_min), "--max", str(s_max)])
                
            except Exception as e:
                print(f"[WARN] Could not launch legend window: {e}")

        # --- 4. INTERACTION (CAMERAS FIX) ---
        def on_keypress(event):
            key = event.keypress
            if not key: return
            
            cam = scene.plotter.camera
            
            # Calculate dynamic center
            if self.root_actor:
                center = self.root_actor.center_of_mass()
            else:
                center = [6500, 3800, 5600] 

            # Raw distance to direct the camera
            OFFSET = 20000 

            if key == 'z': # TOP (Dorsal)
                print("View: Top (Z)")
                cam.SetPosition(center[0], center[1] - OFFSET, center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, 0, -1) 
                scene.plotter.reset_camera()

            elif key == 'x': # SIDE (Sagittal)
                print("View: Side (X)")
                cam.SetPosition(center[0], center[1], center[2] + OFFSET)
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()

            elif key == 'y': # FRONT (Coronal)
                print("View: Front (Y)")
                cam.SetPosition(center[0] - OFFSET, center[1], center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()
            
            elif key == 's': # SAVE
                save_dir = output_dir if output_dir else self.default_scenes_dir
                save_dir.mkdir(exist_ok=True, parents=True)
                timestamp = datetime.now().strftime("%H%M%S")
                
                png_path = save_dir / f"shot_{timestamp}.png"
                scene.screenshot(name=str(png_path))
                print(f"[SAVE] PNG saved: {png_path}")

            elif key == 'k': # STYLE TOGGLE
                # Toggle between wireframe and surface for the root actor
                if self.root_actor:
                    # This is a simple toggle logic
                    # We can't easily check current state in vedo/brainrender wrapper sometimes
                    # So we just re-apply wireframe or surface?
                    # Actually brainrender actors have .wireframe() method.
                    pass
                print("[STYLE] Style toggle not fully implemented yet, preserving keybind.")

            # Force render update
            scene.plotter.render()

        scene.plotter.add_callback('keypress', on_keypress)

        print("\n--- RENDER LOOP ---")
        scene.render()
        return []