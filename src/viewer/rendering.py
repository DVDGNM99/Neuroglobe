import traceback
import yaml
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from brainglobe_atlasapi import BrainGlobeAtlas
from brainrender import Scene, settings, actors
from vedo import Text2D, Sphere, Volume

# --- LOAD CONFIGURATION ---
from src.definitions import PROJECT_ROOT, CONFIGS_DIR
from src.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "visual_config.yaml"

def load_visual_config():
    if not CONFIG_PATH.exists():
        log.warning(f"[WARN] Visual config not found at {CONFIG_PATH}. Using defaults.")
        return {}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

VISUAL_CONFIG = load_visual_config()
AESTHETICS = VISUAL_CONFIG.get("aesthetics", {})
ALIGNMENT = VISUAL_CONFIG.get("alignment", {})
MANUAL_SHIFT = ALIGNMENT.get("manual_shift", {"x": 0, "y": 0, "z": 0})
MANUAL_ROTATION = ALIGNMENT.get("manual_rotation", {"x": 0, "y": 0, "z": 0})

# --- AESTHETIC CONFIGURATION ---
settings.SHOW_AXES = AESTHETICS.get("show_axes", False)
settings.WHOLE_SCREEN = AESTHETICS.get("whole_screen", False)
settings.BACKGROUND_COLOR = AESTHETICS.get("background_color", "white")
settings.SCREENSHOT_TRANSPARENT_BACKGROUND = AESTHETICS.get("screenshot_transparent_background", True)

# --- ALIGNMENT CONFIGURATION ---
ROTATION_MODE = ALIGNMENT.get("rotation_mode", "final_y_270")

# --- MANUAL FINE TUNING ---
SHIFT_X = MANUAL_SHIFT.get("x", 0)
SHIFT_Y = MANUAL_SHIFT.get("y", 0)
SHIFT_Z = MANUAL_SHIFT.get("z", 0)

ROTATE_X = MANUAL_ROTATION.get("x", 0)
ROTATE_Y = MANUAL_ROTATION.get("y", 90)
ROTATE_Z = MANUAL_ROTATION.get("z", 0)

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        log.info(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        
        self.root_dir = PROJECT_ROOT
        self.default_scenes_dir = self.root_dir / "scenes"



    def render_scene(self, region_config: list, tract_file: Path = None, alpha=0.5, output_dir: Path = None, metadata: dict = None, visualization_mode="density", show_legend=True, data_mode="Mean"):
        scene = Scene(atlas_name=self.atlas_name, title="")
        
        # --- 0. CONTEXT (ROOT) ---
        self.root_actor = None
        try:
            log.debug("[DEBUG] Attempting to add 'root' region...")
            # Try standard method
            self.root_actor = scene.add_brain_region("root", alpha=0.05, color="grey")
            if self.root_actor is None:
                 log.warning("[WARN] add_brain_region('root') returned None. Trying scene.root...")
                 pass
            else:
                log.debug("[DEBUG] Root actor created successfully.")
                self.root_actor.wireframe()
                
        except Exception as e: 
            log.warning(f"[WARN] Root load issue: {e}")

        # --- 1. Target Regions ---
        log.info(f"Building scene with {len(region_config)} regions (Mode: {data_mode})...")
        
        midline_x = 5700 # Approximate CCFv3 midline

        for item in region_config:
            acronym = item['acronym']
            try:
                if data_mode == "Both":
                    # --- SPLIT VIEW LOGIC ---
                    c_left = item.get('color_left', '#FFFFFF')
                    c_right = item.get('color_right', '#FFFFFF')
                    
                    # 1. Left Actor (Keep X < 5700)
                    # Normal (1, 0, 0) at origin (5700,0,0) removes everything with X > 5700? 
                    # brainrender/vedo cut_with_plane usually cuts the "positive side" of the plane normal.
                    # So Normal(1,0,0) cuts +X side -> Keeps Left. Correct.
                    actor_left = scene.add_brain_region(acronym, alpha=alpha, color=c_left)
                    if actor_left:
                        actor_left.cut_with_plane(origin=(midline_x, 0, 0), normal=(1, 0, 0))
                        actor_left.name = f"{acronym}_L"
                        actor_left.caption(f"{acronym} (L)")
                    
                    # 2. Right Actor (Keep X > 5700)
                    # Normal (-1, 0, 0) cuts -X side (Left) -> Keeps Right. Correct.
                    actor_right = scene.add_brain_region(acronym, alpha=alpha, color=c_right)
                    if actor_right:
                        actor_right.cut_with_plane(origin=(midline_x, 0, 0), normal=(-1, 0, 0))
                        actor_right.name = f"{acronym}_R"
                        actor_right.caption(f"{acronym} (R)")

                else:
                    # --- STANDARD VIEW LOGIC ---
                    # Add region and capture the actor
                    reg_actor = scene.add_brain_region(acronym, alpha=alpha, color=item['color'])
                    if reg_actor:
                        # FORCE the name to be the acronym so picking works
                        reg_actor.name = acronym
            except Exception as e:
                log.warning(f"[WARN] Failed to add region {acronym}: {e}")

        # --- 2. Tractography / Streamlines ---
        if tract_file and tract_file.exists():
            log.info(f"[RENDER] Loading: {tract_file.name} (Mode: {visualization_mode})")
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
                        log.info("[RENDER] Loaded mesh directly.")

                # CASE B: Streamlines JSON (.json)
                elif tract_file.suffix == ".json" and "Streamlines" in visualization_mode:
                    from brainrender.actors import Streamlines
                    log.info(f"[RENDER] Loading Streamlines from {tract_file.name}")
                    # Brainrender Streamlines actor can load from file path
                    tract_actor = Streamlines(str(tract_file))
                    tract_actor.alpha(0.6)
                    tract_actor.name = "Streamlines"
                    
                # CASE C: Raw Volume (.nrrd)
                else:
                    log.debug(f"[DEBUG] Attempting to load Volume: {tract_file}")
                    vol = Volume(str(tract_file))
                    dmin, dmax = vol.scalar_range()
                    log.info(f"[RENDER] Volume Range: {dmin:.4f} - {dmax:.4f}")
                    
                    if dmax > 0:
                        # Thresholding logic
                        threshold_val = dmax * 0.10 
                        if "Raw" in visualization_mode:
                            threshold_val = dmax * 0.05 
                        elif "Filtered" in visualization_mode:
                            threshold_val = dmax * 0.05
                            
                        log.debug(f"[DEBUG] Thresholding at {threshold_val:.4f} (Mode: {visualization_mode})")

                        tract_actor = vol.isosurface(value=threshold_val)
                        
                        # --- AUTO-SCALING FIX ---
                        # Check if dimensions are in pixels instead of microns
                        # Brain is >5000 microns. If bounds < 1000, it's likely unscaled.
                        bounds = tract_actor.bounds()
                        max_dim = max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4])
                        
                        if max_dim < 2000: # Threshold for "too small"
                            log.warning(f"[WARN] TractCloud is tiny (MaxDim={max_dim:.1f}). Applying auto-scaling (x25)...")
                            # We assume 25um resolution if not specified
                            res = self.atlas.resolution 
                            # self.atlas.resolution is usually a tuple (25, 25, 25)
                            # If it's a single number, handle it
                            if isinstance(res, (tuple, list, np.ndarray)):
                                tract_actor.scale([res[0], res[1], res[2]])
                            else:
                                tract_actor.scale(res)
                            
                            log.info(f"[ALIGN] Scaled cloud to microns.")

                        # Apply Viridis Colormap
                        tract_actor.cmap("viridis", vmin=threshold_val, vmax=dmax)
                        tract_actor.alpha(0.6)
                        tract_actor.name = "Tractography (Density)"
                        
                    else:
                        log.warning("[WARNING] Volume is empty (dmax=0).")

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
                        log.info(f"[ALIGN] Applying Manual Rotation: X={ROTATE_X}, Y={ROTATE_Y}, Z={ROTATE_Z}")
                        log.debug(f"[ALIGN] Pivot Point: {pivot_point}")
                        
                        if ROTATE_X != 0: tract_actor.rotate(ROTATE_X, axis=(1,0,0), point=pivot_point)
                        if ROTATE_Y != 0: tract_actor.rotate(ROTATE_Y, axis=(0,1,0), point=pivot_point)
                        if ROTATE_Z != 0: tract_actor.rotate(ROTATE_Z, axis=(0,0,1), point=pivot_point)

                    # Apply Manual Fine Tuning
                    log.info(f"[ALIGN] Applying Manual Shift: {SHIFT_X}, {SHIFT_Y}, {SHIFT_Z}")
                    
                    com_before = tract_actor.center_of_mass()
                    log.debug(f"[DEBUG] CoM Before: {com_before}")
                    
                    tract_actor.shift(SHIFT_X, SHIFT_Y, SHIFT_Z)
                    
                    com_after = tract_actor.center_of_mass()
                    log.debug(f"[DEBUG] CoM After:  {com_after}")
                    
                    # Sanity check: Did it move?
                    diff = np.array(com_after) - np.array(com_before)
                    log.debug(f"[DEBUG] Actual Movement: {diff}")
                        
                scene.add(tract_actor)

            except Exception as e:
                log.error(f"[ERROR] Tract render failed: {e}")
                traceback.print_exc()

        # --- 3. HUD & LEGEND ---
        hud = Text2D("S: Save | K: Style | X/Y/Z: Views", pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)


        if show_legend:
            log.info("[RENDER] Legend is disabled in this version for stability.")

        # --- 4. INTERACTION (CAMERAS & SAVING) ---
        self.output_dir = output_dir
        self.metadata = metadata
        self.current_save_dir = None # Track the folder for this session
        
        # We need the seed name for the folder name
        self.seed_name = "UnknownSeed"
        if metadata and "experiment_seed" in metadata:
            self.seed_name = metadata["experiment_seed"]

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
                log.info("View: Top (Z)")
                cam.SetPosition(center[0], center[1] - OFFSET, center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, 0, -1) 
                scene.plotter.reset_camera()

            elif key == 'x': # SIDE (Sagittal)
                log.info("View: Side (X)")
                cam.SetPosition(center[0], center[1], center[2] + OFFSET)
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()

            elif key == 'y': # FRONT (Coronal)
                log.info("View: Front (Y)")
                cam.SetPosition(center[0] - OFFSET, center[1], center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()
            
            elif key == 's': # SAVE
                if not self.output_dir:
                    log.warning("[WARN] No output directory set. Cannot save.")
                    return

                try:
                    # 1. Generate Timestamp & Folder (ONLY ONCE PER SESSION)
                    if self.current_save_dir is None:
                        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        folder_name = f"{self.seed_name}_{timestamp}"
                        self.current_save_dir = self.output_dir / folder_name
                        self.current_save_dir.mkdir(parents=True, exist_ok=True)
                        log.info(f"[SYSTEM] Created Session Folder: {self.current_save_dir.absolute()}")
                        
                        # Save Metadata ONCE when folder is created
                        if self.metadata:
                            self.metadata["saved_at"] = timestamp
                            self.metadata["folder_name"] = folder_name
                            
                            json_path = self.current_save_dir / "metadata.json"
                            with open(json_path, 'w') as f:
                                json.dump(self.metadata, f, indent=4)
                            log.info(f"[SAVE] Metadata saved: {json_path.name}")
                        else:
                            log.warning("[WARN] No metadata to save.")

                    # 2. Save Screenshot (PNG) - Unique name per shot
                    shot_time = datetime.now().strftime("%H-%M-%S")
                    screenshot_path = self.current_save_dir / f"screenshot_{shot_time}.png"
                    
                    # vedo screenshot
                    scene.screenshot(str(screenshot_path))
                    log.info(f"[SAVE] Screenshot saved: {screenshot_path.name}")

                    # 3. Save Vector SVG (Optional/Experimental)
                    # Only try to save SVG if it doesn't exist or user wants multiple?
                    # Let's save one per screenshot to match view
                    # 3. Export Geometry (OBJ) - REMOVED (Dead Code Cleanup)
                    # Implementation moved to future feature backlog
                    pass
                    
                    # Visual Feedback
                    log.info("[SUCCESS] Saved!")
                    
                except Exception as e:
                    log.error(f"[ERROR] Save failed: {e}")
                    import traceback
                    traceback.print_exc()

            elif key == 'k': # STYLE TOGGLE
                # Toggle between wireframe and surface for the root actor
                if self.root_actor:
                    pass
                log.info("[STYLE] Style toggle not fully implemented yet, preserving keybind.")

            # Force render update
            scene.plotter.render()

        scene.plotter.add_callback('keypress', on_keypress)

        log.info("\n--- RENDER LOOP ---")
        # Use scene.render() for interactive window!
        scene.render(interactive=True, zoom=1.2)
        log.info("--- SCENE CLOSED ---")
        return []