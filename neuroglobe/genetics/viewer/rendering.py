import json
import numpy as np
import traceback

from neuroglobe.genetics.definitions import PROJECT_ROOT, CONFIGS_DIR, PROCESSED_DATA_DIR

MANIFEST_PATH = CONFIGS_DIR / "manifest.json"
RUNTIME_STATE_PATH = CONFIGS_DIR / "runtime_state.json"

def load_manifest():
    if not MANIFEST_PATH.exists():
        print(f"[WARN] Manifest not found at {MANIFEST_PATH}.")
        return {}
    with open(MANIFEST_PATH, "r") as f:
        return json.load(f)

MANIFEST = load_manifest()
AESTHETICS = MANIFEST.get("aesthetics", {})

class GeneticsRenderEngine:
    def __init__(self, atlas_name="allen_mouse_25um", runtime_state_path=None):
        from brainglobe_atlasapi import BrainGlobeAtlas

        print(f"Initializing Atlas: {atlas_name}...")
        self.atlas = BrainGlobeAtlas(atlas_name)
        self.atlas_name = atlas_name
        self.root_dir = PROJECT_ROOT
        self.runtime_state_path = (
            runtime_state_path if runtime_state_path is not None else RUNTIME_STATE_PATH
        )

    def render_genes(self):
        from brainrender import Scene, settings
        from vedo import Text2D, Volume

        settings.SHOW_AXES = AESTHETICS.get("show_axes", False)
        settings.WHOLE_SCREEN = AESTHETICS.get("whole_screen", False)
        settings.BACKGROUND_COLOR = AESTHETICS.get("background_color", "white")
        settings.SCREENSHOT_TRANSPARENT_BACKGROUND = AESTHETICS.get(
            "screenshot_transparent_background", True
        )
        scene = Scene(atlas_name=self.atlas_name, title="Genetics Expression Viewer")

        # 0. Root Context
        try:
            self.root_actor = scene.add_brain_region("root", alpha=0.05, color="grey")
            if self.root_actor:
                self.root_actor.wireframe()
        except Exception as e:
            print(f"[WARN] Root load issue: {e}")

        # 1. Target Regions Reference Meshes
        target_regions = MANIFEST.get("processing", {}).get("target_regions", [])
        genes = MANIFEST.get("processing", {}).get("genes", [])

        # Override with interactive GUI state if available
        if self.runtime_state_path.exists():
            try:
                with open(self.runtime_state_path, "r") as f:
                    state = json.load(f)
                    target_regions = state.get("selected_regions", target_regions)
                    genes = state.get("selected_genes", genes)
            except Exception as e:
                print(f"[WARN] Failed to load runtime state: {e}")

        alpha_val = AESTHETICS.get("default_alpha", 0.3)
        print(f"Adding Reference Regions: {target_regions}")

        # Use a soft gray or standard aesthetic color for the masks
        for acronym in target_regions:
            try:
                # Add region
                reg_actor = scene.add_brain_region(acronym, alpha=alpha_val, color="lightgrey")
                if reg_actor:
                    reg_actor.name = acronym
                    # Wireframe could be nice to let voxels shine through
                    reg_actor.wireframe()
            except Exception as e:
                print(f"[WARN] Failed to add region {acronym}: {e}")

        # 2. Volumes
        colors = MANIFEST.get("gene_colors", {})

        for gene in genes:
            file_path = PROCESSED_DATA_DIR / f"{gene}_filtered.nrrd"

            if not file_path.exists():
                # Fallback to Capitalized first letter (Allen API sometimes returns lowercase or specific case)
                file_path_alt = PROCESSED_DATA_DIR / f"{gene.capitalize()}_filtered.nrrd"
                if file_path_alt.exists():
                    file_path = file_path_alt
                else:
                    print(f"[WARN] Filtered data for {gene} not found at {file_path.name}.")
                    continue

            print(f"Loading {gene} from {file_path.name}...")
            try:
                vol = Volume(str(file_path))
                arr = vol.tonumpy()
                non_zero = arr[arr > 0]

                if len(non_zero) == 0:
                    print(f"[WARN] {gene} volume is empty in selected regions.")
                    continue

                # Setup Thresholding for Voxels (Lego blocks)
                threshold = np.percentile(non_zero, 90) # top 10%
                print(f"[{gene}] Generating Lego Voxels (Threshold: {threshold:.2f})...")

                lego = vol.legosurface(vmin=threshold)

                gene_color = colors.get(gene, "red")

                # Apply specific color
                lego.c(gene_color)
                lego.alpha(0.5) # Increased transparency (pastel look)
                lego.name = gene

                scene.add(lego)

            except Exception as e:
                print(f"[ERROR] Failed to load {gene} volume: {e}")
                traceback.print_exc()

        # 3. HUD
        hud = Text2D("Voxel Expression (Lego-style) | S: Save | X/Y/Z: Views", pos="bottom-left", s=0.9, c="black", font="Calco")
        scene.add(hud)

        # 4. Interaction
        def on_keypress(event):
            key = event.keypress
            if not key: return

            cam = scene.plotter.camera
            center = [6500, 3800, 5600]
            OFFSET = 20000

            if key == 'z':
                cam.SetPosition(center[0], center[1] - OFFSET, center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, 0, -1)
                scene.plotter.reset_camera()
            elif key == 'x':
                cam.SetPosition(center[0], center[1], center[2] + OFFSET)
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()
            elif key == 'y':
                cam.SetPosition(center[0] - OFFSET, center[1], center[2])
                cam.SetFocalPoint(center[0], center[1], center[2])
                cam.SetViewUp(0, -1, 0)
                scene.plotter.reset_camera()

            scene.plotter.render()

        scene.plotter.add_callback('keypress', on_keypress)
        print("\n--- RENDER LOOP ---")
        scene.render(interactive=True, zoom=1.2)
        print("--- SCENE CLOSED ---")

def main() -> int:
    engine = GeneticsRenderEngine()
    engine.render_genes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
