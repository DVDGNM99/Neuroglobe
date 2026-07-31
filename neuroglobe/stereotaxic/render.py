import argparse
import queue
import sys
import os
import threading

def render_scene(acronyms, frontal_slice):
    os.environ.setdefault("BRAINRENDER_LOG_LEVEL", "INFO")
    from brainrender import Scene, settings
    from vedo import Text2D
    import vtk

    settings.SHOW_AXES = False
    print(f"[INFO] Initializing BrainRender Scene...")
    scene = Scene(title="Neuroglobe Stereotaxic Viewer", atlas_name="allen_mouse_25um")

    # We need to keep references to all actors to slice them dynamically
    all_actors = []

    # --- 1. Background Boundaries (Macro Regions) ---
    macro_regions = ["Isocortex", "OLF", "HPF", "CTXsp", "STR", "PAL", "TH", "HY", "MB", "P", "MY", "CB"]
    print(f"[INFO] Loading {len(macro_regions)} structural boundaries for anatomical context...")
    for macro in macro_regions:
        try:
            # We add them with very low alpha and a neutral color (e.g. gray or light gray)
            actor = scene.add_brain_region(macro, alpha=0.1, color="silver", silhouette=False)
            if actor: all_actors.append(actor)
        except Exception as e:
            pass # Ignore if a specific macro region is not found in the atlas hierarchy

    # --- 2. Add Selected Regions as Wireframe ---
    added_count = 0
    # Provide a distinct color palette
    colors = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c"]

    for idx, acr in enumerate(acronyms):
        try:
            print(f"[INFO] Adding target region: {acr}")
            region_color = colors[idx % len(colors)]
            actor = scene.add_brain_region(acr.strip(), alpha=0.9, color=region_color)
            if actor:
                # Trasformiamo la mesh riempita in una mesh wireframe (a griglia)
                actor.wireframe(True)
                # Facoltativo: per renderla più visibile possiamo aumentare lo spessore delle linee
                try:
                    actor.lw(2) # Line width
                except:
                    pass
                all_actors.append(actor)
            added_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to load region '{acr}': {e}")

    if added_count == 0:
        print("[ERROR] No targets loaded successfully.")

    # Remove old static cut: The scene.slice("frontal") is destructive and cannot be moved dynamically.
    # Instead, we will use a Vedo cutting plane that updates continuously.

    # --- HUD & KEYBINDS FOR AXIS SNAPPING ---
    hud = Text2D("3D Controls | X: Side | Y: Front | Z: Top | Hover: Coords", pos="bottom-left", s=0.9, c="black", font="Calco")
    scene.add(hud)

    # --- 3. Dynamic Stereotaxic Coordinates & Mouse Hover ---
    # We use Standard Approx for allen_mouse_25um based on literature coordinates mapping:
    # AP: Bregma is at pixel ~215 -> 5375 um
    # DV: Bregma is at surface ~ 0 um
    # ML: Bregma is at midline -> 5700 um
    BREGMA_AP_UM = 5375
    BREGMA_ML_UM = 5700
    BREGMA_DV_UM = 200 # Approx surface

    def on_mouse_move(event):
        # In vedo, event.picked3d gives the 3D coordinates in microns
        coords = event.picked3d
        if coords is not None and len(coords) == 3:
            # Convert to mm centered on Bregma
            # Note: Allen ARA orientations: X is AP (front to back), Y is DV (top to bottom), Z is ML (left to right)
            ap_mm = -(coords[0] - BREGMA_AP_UM) / 1000.0  # + indicates anterior to bregma
            dv_mm = -(coords[1] - BREGMA_DV_UM) / 1000.0  # + indicates ventral to bregma (depth)
            ml_mm = (coords[2] - BREGMA_ML_UM) / 1000.0   # + indicates right hemisphere

            # Print strictly formatted string for the GUI to parse
            print(f"COORD_APPROX|{ap_mm:.1f}|{ml_mm:.1f}|{dv_mm:.1f}", flush=True)

    def on_keypress(event):
        key = event.keypress
        if not key: return

        cam = scene.plotter.camera

        # Center of Allen Atlas
        center = [6500, 3800, 5600]
        OFFSET = 20000

        if key == 'z': # TOP (Dorsal)
            cam.SetPosition(center[0], center[1] - OFFSET, center[2])
            cam.SetFocalPoint(center[0], center[1], center[2])
            cam.SetViewUp(0, 0, -1)
            scene.plotter.reset_camera()

        elif key == 'x': # SIDE (Sagittal)
            cam.SetPosition(center[0], center[1], center[2] + OFFSET)
            cam.SetFocalPoint(center[0], center[1], center[2])
            cam.SetViewUp(0, -1, 0)
            scene.plotter.reset_camera()

        elif key == 'y': # FRONT (Coronal)
            cam.SetPosition(center[0] - OFFSET, center[1], center[2])
            cam.SetFocalPoint(center[0], center[1], center[2])
            cam.SetViewUp(0, -1, 0)
            scene.plotter.reset_camera()

        scene.plotter.render()

    # IPC Slider Listener
    # 1. Create a single clipping plane for all actors
    clip_plane = vtk.vtkPlane()
    clip_plane.SetNormal(1, 0, 0) # Normal facing Anterior-Posterior
    # The brain length is approx AP 0 to 13000 um. We start the plane at 0
    clip_plane.SetOrigin(0, 0, 0)

    # If the user toggled the "Coronal Frontal Slice" on launch, we initialize it active at center
    if frontal_slice:
        clip_plane.SetOrigin(5400, 0, 0) # Near bregma

    for act in all_actors:
        # Brainrender actors wrap vedo actors. The underlying vtk actor holds mappers.
        try:
            # act.mesh is the vedo Mesh object
            mapper = act.mesh.mapper()
            mapper.AddClippingPlane(clip_plane)
        except Exception as e:
            pass

    pending_slices: queue.SimpleQueue[float] = queue.SimpleQueue()

    def ipc_listener_thread():
        # Listens on stdin for commands generated by the GUI slider
        # Command syntax: SLICE|AP_MICRONS
        for line in sys.stdin:
            line = line.strip()
            if line.startswith("SLICE|"):
                try:
                    ap_val = float(line.split("|")[1])
                    if 0.0 <= ap_val <= 13200.0:
                        pending_slices.put(ap_val)
                except (ValueError, IndexError):
                    print("[WARN] Invalid SLICE command.", flush=True)

    # Start thread as daemon so it dies with the process
    threading.Thread(target=ipc_listener_thread, daemon=True).start()

    def apply_pending_slices(_caller=None, _event=None):
        latest = None
        while True:
            try:
                latest = pending_slices.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            clip_plane.SetOrigin(latest, 0, 0)
            scene.plotter.render()
            print(f"SLICE_ACK|{latest:.0f}", flush=True)

    # VTK objects are mutated only from the render thread.
    interactor = scene.plotter.interactor
    interactor.AddObserver("TimerEvent", apply_pending_slices)
    interactor.CreateRepeatingTimer(50)

    print(f"[INFO] Rendering scene...")

    scene.plotter.add_callback('keypress', on_keypress)
    scene.plotter.add_callback('MouseMove', on_mouse_move)
    scene.render(interactive=True)
    print(f"[INFO] Scene closed.")

def main() -> int:
    parser = argparse.ArgumentParser(description="Neuroglobe Stereotaxic Renderer")
    parser.add_argument("--regions", type=str, required=True, help="Comma separated acronyms to render")
    parser.add_argument("--coronal", action="store_true", help="Apply frontal slice to the render")
    args = parser.parse_args()

    acronyms_list = [a.strip() for a in args.regions.split(",") if a.strip()]

    if not acronyms_list:
        print("[ERROR] No valid regions found to render.")
        return 1

    render_scene(acronyms_list, args.coronal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
