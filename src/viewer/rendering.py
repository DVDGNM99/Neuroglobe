import yaml
import numpy as np
from pathlib import Path
from datetime import datetime
from brainglobe_atlasapi import BrainGlobeAtlas
from brainrender import Scene, settings, actors
from vedo import Text2D, Sphere, Volume

# --- CONFIGURAZIONE ESTETICA ---
settings.SHOW_AXES = False
settings.WHOLE_SCREEN = False
settings.BACKGROUND_COLOR = "white"
settings.SCREENSHOT_TRANSPARENT_BACKGROUND = True

BREGMA_CENTER = [6500, 3800, 5600]

# --- CONFIGURAZIONE ROTAZIONE (LOCALE) ---
ROTATION_MODE = "final_y_270"

# --- CONFIGURAZIONE SPOSTAMENTO FINE (TRASLAZIONE) ---
# Unità = MICRON (1000 = 1 mm)
# Modifica questi valori per allineare la nuvola blu
SHIFT_X = 400  # + va dx, - va sx
SHIFT_Y = -50  # + va giù (Ventrale), - va su (Dorsale)
SHIFT_Z = -200   # + va dietro, - va avanti

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        print(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.default_scenes_dir = self.root_dir / "scenes"

    def validate_regions(self, regions: list) -> tuple:
        valid = []
        invalid = []
        for r in regions:
            try:
                _ = self.atlas.structure_from_acronym(r)
                valid.append(r)
            except Exception:
                invalid.append(r)
        return valid, invalid

    def render_scene(self, region_config: list, tract_file: Path = None, alpha=0.5, output_dir: Path = None, metadata: dict = None):
        """
        Render engine con Rotazione + Shift Manuale.
        """
        scene = Scene(atlas_name=self.atlas_name, title="")
        
        # --- 0. CONTESTO (ROOT) ---
        try:
            scene.add_brain_region("root", alpha=0.1, color="grey").wireframe()
        except Exception as e:
            print(f"[WARNING] Could not add root: {e}")

        # --- 1. Regioni Target ---
        print(f"Building scene with {len(region_config)} regions...")
        for item in region_config:
            try:
                scene.add_brain_region(item['acronym'], alpha=alpha, color=item['color'])
            except: pass

        # --- 2. Tractography (LOAD & ALIGN) ---
        if tract_file and tract_file.exists():
            print(f"[RENDER] Loading Tractography: {tract_file.name}")
            try:
                vol = Volume(str(tract_file))
                dmin, dmax = vol.scalar_range()
                
                if dmax > 0:
                    threshold_val = dmax * 0.10
                    tract_actor = vol.isosurface(value=threshold_val)
                    
                    # --- A. FIX PIVOT & ROTATION ---
                    center = tract_actor.center_of_mass()
                    print(f"[ALIGN] Center of Mass: {center}")
                    
                    if ROTATION_MODE == "standard":
                        tract_actor.rotate(-90, axis=(1,0,0), point=center)
                        tract_actor.rotate(180, axis=(0,0,1), point=center)
                    elif ROTATION_MODE == "final_y_270":
                         print("[ALIGN] Applying Rotation: Y 270")
                         tract_actor.rotate(270, axis=(0,1,0), point=center)

                    # --- B. FIX TRASLAZIONE (SHIFT FINE) ---
                    print(f"[ALIGN] Applying Manual Shift: X={SHIFT_X}, Y={SHIFT_Y}, Z={SHIFT_Z}")
                    # .shift() sposta l'attore di dx, dy, dz rispetto alla posizione corrente
                    tract_actor.shift(SHIFT_X, SHIFT_Y, SHIFT_Z)

                    tract_actor.c("blue").alpha(0.4)
                    scene.add(tract_actor)
                    print("[RENDER] Tracts added and aligned.")
                else:
                    print("[WARNING] Volume is empty.")

            except Exception as e:
                print(f"[ERROR] Tract render failed: {e}")

        # --- 3. HUD ---
        legend_text = (
            "CONTROLS:\n"
            "[X/Y/Z] Views\n"
            "[S] Save Scene (PNG+SVG)"
        )
        hud = Text2D(legend_text, pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)

        # --- 4. Colorbar ---
        try:
            dummy = Sphere(r=0).pos(0,0,0).alpha(0)
            dummy.cmap("plasma", [0,1])
            scene.add(dummy)
            scene.plotter.add_scalar_bar(dummy, title="Density", pos=(0.85, 0.05), c="black")
        except: pass

        # --- 5. INTERAZIONE ---
        def on_keypress(event):
            key = event.keypress
            if not key: return
            cam = scene.plotter.camera
            
            if key == 'z':
                cam.SetPosition(BREGMA_CENTER[0], -10000, BREGMA_CENTER[2])
                cam.SetFocalPoint(BREGMA_CENTER[0], BREGMA_CENTER[1], BREGMA_CENTER[2])
                cam.SetViewUp(1, 0, 0)
                scene.plotter.reset_camera()
            elif key == 'x':
                cam.SetPosition(BREGMA_CENTER[0], BREGMA_CENTER[1], 20000)
                cam.SetFocalPoint(BREGMA_CENTER[0], BREGMA_CENTER[1], BREGMA_CENTER[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()
            elif key == 'y':
                cam.SetPosition(20000, BREGMA_CENTER[1], BREGMA_CENTER[2])
                cam.SetFocalPoint(BREGMA_CENTER[0], BREGMA_CENTER[1], BREGMA_CENTER[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()
            
            elif key == 's':
                if output_dir:
                    save_dir = output_dir
                else:
                    save_dir = self.default_scenes_dir
                    save_dir.mkdir(exist_ok=True, parents=True)

                timestamp_shot = datetime.now().strftime("%H%M%S")
                
                # --- SAVE PNG ---
                png_path = save_dir / f"screenshot_{timestamp_shot}.png"
                scene.screenshot(name=str(png_path))
                print(f"\n[SAVE] PNG saved to: {png_path}")

                # --- SAVE SVG ---
                svg_path = save_dir / f"screenshot_{timestamp_shot}.svg"
                print(f"[SAVE] Attempting SVG export...")
                try:
                    scene.plotter.screenshot(str(svg_path))
                    print(f"[SAVE] SVG saved to: {svg_path}")
                except Exception as e:
                    print(f"[ERROR] SVG Export failed: {e}")

                try:
                     with open(save_dir / "metadata.yml", 'w') as f:
                        yaml.dump(metadata, f, sort_keys=False)
                except: pass

        scene.plotter.add_callback('keypress', on_keypress)

        print("\n--- RENDER LOOP ---")
        scene.render()
        return []