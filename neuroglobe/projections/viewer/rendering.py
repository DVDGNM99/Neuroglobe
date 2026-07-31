import traceback
import yaml
import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

# --- LOAD CONFIGURATION ---
from neuroglobe.core.coordinates import AtlasGeometry, PhysicalAxis
from neuroglobe.projections.definitions import PROJECT_ROOT, CONFIGS_DIR
from neuroglobe.projections.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "visual_config.yaml"

def load_visual_config():
    if not CONFIG_PATH.exists():
        log.warning(f"[WARN] Visual config not found at {CONFIG_PATH}. Using defaults.")
        return {}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

VISUAL_CONFIG = load_visual_config()
AESTHETICS = VISUAL_CONFIG.get("aesthetics", {})

@dataclass
class RenderResult:
    success: bool
    regions_added: int = 0
    tract_loaded: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        from brainglobe_atlasapi import BrainGlobeAtlas

        log.info(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        
        self.root_dir = PROJECT_ROOT
        self.default_scenes_dir = self.root_dir / "scenes"



    def render_scene(self, region_config: list, tract_file: Path = None, alpha=0.5, output_dir: Path = None, metadata: dict = None, visualization_mode="density", show_legend=True, data_mode="Mean"):
        from brainrender import Scene, settings
        from vedo import LegendBox, Text2D, Volume

        settings.SHOW_AXES = AESTHETICS.get("show_axes", False)
        settings.WHOLE_SCREEN = AESTHETICS.get("whole_screen", False)
        settings.BACKGROUND_COLOR = AESTHETICS.get("background_color", "white")
        settings.SCREENSHOT_TRANSPARENT_BACKGROUND = AESTHETICS.get(
            "screenshot_transparent_background", True
        )
        result = RenderResult(success=False)
        scene = Scene(atlas_name=self.atlas_name, title="")
        legend_actors = []
        
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
            result.warnings.append(f"Root region: {e}")

        # --- 1. Target Regions ---
        log.info(f"Building scene with {len(region_config)} regions (Mode: {data_mode})...")
        
        geometry = AtlasGeometry.from_values(
            self.atlas.annotation.shape, self.atlas.resolution
        )
        midline_ml = geometry.midpoint_um(PhysicalAxis.ML)

        for item in region_config:
            acronym = item['acronym']
            try:
                if data_mode == "Both":
                    # --- SPLIT VIEW LOGIC ---
                    c_left = item.get('color_left', '#FFFFFF')
                    c_right = item.get('color_right', '#FFFFFF')
                    
                    # Split on physical ML (Z), not AP (X).
                    actor_left = scene.add_brain_region(acronym, alpha=alpha, color=c_left)
                    if actor_left:
                        actor_left.cut_with_plane(
                            origin=(0, 0, midline_ml), normal=(0, 0, 1)
                        )
                        actor_left.name = f"{acronym}_L"
                        actor_left.caption(f"{acronym} (L)")
                        legend_actors.append(actor_left)
                    
                    # 2. Right Actor (Keep X > 5700)
                    # Normal (-1, 0, 0) cuts -X side (Left) -> Keeps Right. Correct.
                    actor_right = scene.add_brain_region(acronym, alpha=alpha, color=c_right)
                    if actor_right:
                        actor_right.cut_with_plane(
                            origin=(0, 0, midline_ml), normal=(0, 0, -1)
                        )
                        actor_right.name = f"{acronym}_R"
                        actor_right.caption(f"{acronym} (R)")
                        legend_actors.append(actor_right)
                    if actor_left or actor_right:
                        result.regions_added += 1

                else:
                    # --- STANDARD VIEW LOGIC ---
                    # Add region and capture the actor
                    reg_actor = scene.add_brain_region(acronym, alpha=alpha, color=item['color'])
                    if reg_actor:
                        # FORCE the name to be the acronym so picking works
                        reg_actor.name = acronym
                        legend_actors.append(reg_actor)
                        result.regions_added += 1
            except Exception as e:
                log.warning(f"[WARN] Failed to add region {acronym}: {e}")
                result.errors.append(f"Region {acronym}: {e}")

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
                        
                        # Apply Viridis Colormap
                        tract_actor.cmap("viridis", vmin=threshold_val, vmax=dmax)
                        tract_actor.alpha(0.6)
                        tract_actor.name = "Tractography (Density)"
                        
                    else:
                        log.warning("[WARNING] Volume is empty (dmax=0).")
                        result.errors.append("Tract volume is empty.")

                if tract_actor:
                    # The file header/mesh geometry is the registration source.
                    scene.add(tract_actor)
                    legend_actors.append(tract_actor)
                    result.tract_loaded = True

            except Exception as e:
                log.error(f"[ERROR] Tract render failed: {e}")
                traceback.print_exc()
                result.errors.append(f"Tract render: {e}")

        # --- 3. HUD & LEGEND ---
        hud = Text2D("S: Save | X/Y/Z: Views", pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)


        if show_legend:
            try:
                legend = LegendBox(
                    entries=legend_actors,
                    nmax=20,
                    c="black",
                    bg="white",
                    alpha=0.8,
                    pos="top-right",
                )
                scene.add(legend)
            except Exception as error:
                warning = f"Legend: {error}"
                log.warning("[WARN] %s", warning)
                result.warnings.append(warning)

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

            # Force render update
            scene.plotter.render()

        scene.plotter.add_callback('keypress', on_keypress)

        result.success = result.regions_added > 0 and not result.errors
        if metadata is not None:
            metadata["render_status"] = (
                "success" if result.success else "partial_or_failed"
            )
            metadata["render_errors"] = result.errors
            metadata["render_warnings"] = result.warnings
            metadata["regions_added"] = result.regions_added
            metadata["tract_loaded"] = result.tract_loaded

        log.info("\n--- RENDER LOOP ---")
        # Use scene.render() for interactive window!
        scene.render(interactive=True, zoom=1.2)
        log.info("--- SCENE CLOSED ---")
        return result
