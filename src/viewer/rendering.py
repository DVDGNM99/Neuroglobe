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

# --- CONFIGURAZIONE SPOSTAMENTO FINE ---
SHIFT_X = 600    
SHIFT_Y = -100   
SHIFT_Z = -200   
ROTATION_MODE = "final_y_270"

class RenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um"):
        print(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.default_scenes_dir = self.root_dir / "scenes"

    def render_scene(self, region_config: list, tract_file: Path = None, alpha=0.5, output_dir: Path = None, metadata: dict = None, visualization_mode="density"):
        scene = Scene(atlas_name=self.atlas_name, title="")
        
        # --- 0. CONTESTO (ROOT) ---
        self.root_actor = None
        try:
            self.root_actor = scene.add_brain_region("root", alpha=0.05, color="grey")
            if self.root_actor: self.root_actor.wireframe()
        except Exception as e: 
            print(f"[WARN] Root load issue: {e}")

        # --- 1. Regioni Target ---
        print(f"Building scene with {len(region_config)} regions...")
        for item in region_config:
            try:
                scene.add_brain_region(item['acronym'], alpha=alpha, color=item['color'])
            except: pass

        # --- 2. Tractography / Streamlines ---
        if tract_file and tract_file.exists():
            print(f"[RENDER] Loading: {tract_file.name} (Mode: {visualization_mode})")
            try:
                vol = Volume(str(tract_file))
                dmin, dmax = vol.scalar_range()
                
                if dmax > 0:
                    tract_actor = None
                    
                    if visualization_mode == "density":
                        threshold_val = dmax * 0.15 
                        tract_actor = vol.isosurface(value=threshold_val)
                        tract_actor.c("blue").alpha(0.6)

                    elif visualization_mode == "streamlines":
                        threshold_val = dmax * 0.10
                        tract_actor = vol.isosurface(value=threshold_val)
                        tract_actor.c("cyan").alpha(0.8).lw(1)
                        print("[INFO] Streamlines mode placeholder active")

                    if tract_actor:
                        center = tract_actor.center_of_mass()
                        if ROTATION_MODE == "final_y_270":
                             tract_actor.rotate(270, axis=(0,1,0), point=center)
                        
                        print(f"[ALIGN] Applying Shift: X={SHIFT_X}, Y={SHIFT_Y}, Z={SHIFT_Z}")
                        tract_actor.shift(SHIFT_X, SHIFT_Y, SHIFT_Z)
                        scene.add(tract_actor)
                else:
                    print("[WARNING] Volume is empty.")
            except Exception as e:
                print(f"[ERROR] Tract render failed: {e}")

        # --- 3. HUD ---
        hud = Text2D("S: Save | X/Y/Z: Views (Double Tap)", pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)

        # --- 4. INTERAZIONE (CAMERAS FIX) ---
        def on_keypress(event):
            key = event.keypress
            if not key: return
            
            cam = scene.plotter.camera
            
            # Calcolo centro dinamico
            if self.root_actor:
                center = self.root_actor.center_of_mass()
            else:
                center = [6500, 3800, 5600] 

            # Distanza "grezza" per direzionare la camera
            OFFSET = 20000 

            # NOTA SISTEMA ALLEN:
            # Axis 0 (X): Anterior-Posterior (Avanti-Dietro)
            # Axis 1 (Y): Dorsal-Ventral (Su-Giù)
            # Axis 2 (Z): Left-Right (Sinistra-Destra)

            if key == 'z': # DALL'ALTO (Dorsale)
                print("View: Top (Z)")
                # Posizioniamo la camera "sopra" (Y negativo in Allen è "su" visivamente)
                cam.SetPosition(center[0], center[1] - OFFSET, center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                # ViewUp lungo Z così il naso punta a destra o sinistra, non ruotato strano
                cam.SetViewUp(0, 0, -1) 
                
                # IL FIX: Resetta lo zoom per inquadrare tutto perfettamente
                scene.plotter.reset_camera()

            elif key == 'x': # LATERALE (Sagittale)
                print("View: Side (X)")
                # Guardiamo lungo l'asse Z (da lato)
                cam.SetPosition(center[0], center[1], center[2] + OFFSET)
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                
                scene.plotter.reset_camera() # IL FIX

            elif key == 'y': # FRONTALE (Coronale)
                print("View: Front (Y)")
                # Guardiamo lungo l'asse X (dal fronte/retro)
                cam.SetPosition(center[0] - OFFSET, center[1], center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                
                scene.plotter.reset_camera() # IL FIX
            
            elif key == 's': # SALVATAGGIO
                save_dir = output_dir if output_dir else self.default_scenes_dir
                save_dir.mkdir(exist_ok=True, parents=True)
                timestamp = datetime.now().strftime("%H%M%S")
                
                png_path = save_dir / f"shot_{timestamp}.png"
                scene.screenshot(name=str(png_path))
                print(f"[SAVE] PNG saved: {png_path}")

            # Forza il ricalcolo del rendering
            scene.plotter.render()

        scene.plotter.add_callback('keypress', on_keypress)

        print("\n--- RENDER LOOP ---")
        scene.render()
        return []