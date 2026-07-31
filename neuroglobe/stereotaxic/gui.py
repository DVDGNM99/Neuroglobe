import customtkinter as ctk
import sys
import subprocess
import threading
from pathlib import Path

from neuroglobe.stereotaxic.transform import DEFAULT_STEREOTAXIC_TRANSFORM

# --- Constants & Paths ---
BASE_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_PATH.parents[1]
RENDER_SCRIPT = BASE_PATH / "render.py"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class StereotaxicApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Neuroglobe Stereotaxic")
        self.geometry("750x700")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(main_frame, text="Stereotaxic 3D Viewer", font=("Arial", 22, "bold"))
        title_label.pack(pady=(20, 10))

        desc_label = ctk.CTkLabel(main_frame, text="Visualize BrainGlobe meshes with interactive stereotaxic coordinates.", text_color="gray", font=("Arial", 12))
        desc_label.pack(pady=(0, 10))

        # Regions Checkboxes
        ctk.CTkLabel(main_frame, text="Select Cortical Areas:", font=("Arial", 14, "bold")).pack(anchor="w", padx=30, pady=(10, 5))

        self.region_checkboxes = {}
        # List of areas based on requested demo (dorsal cortex + SSp-bfd + SSp)
        # Using main parent meshes ("mesh parents soltanto")
        default_regions = [
            "FRP", "MOp", "MOs", "SSp", "SSs", "GU", "VISC",
            "AUDd", "AUDp", "AUDpo", "AUDv", "VISal", "VISam",
            "VISl", "VISp", "VISpl", "VISpm", "VISli", "VISpor",
            "ACA", "PL", "ILA", "ORB", "AI", "RSP", "PTLp", "TEa",
            "SSp-bfd"
        ]

        self.regions_scroll = ctk.CTkScrollableFrame(main_frame, height=150)
        self.regions_scroll.pack(fill="x", padx=30, pady=5)

        # Grid layout for checkboxes
        cols = 4
        for i, reg in enumerate(default_regions):
            # Soltanto SSp-bfd pre-selezionata
            is_checked = (reg == "SSp-bfd")
            var = ctk.BooleanVar(value=is_checked)
            chk = ctk.CTkCheckBox(self.regions_scroll, text=reg, variable=var)
            chk.grid(row=i//cols, column=i%cols, padx=10, pady=5, sticky="w")
            self.region_checkboxes[reg] = var

        # Additional Custom Regions Input
        ctk.CTkLabel(main_frame, text="Extra Regions (comma separated):", font=("Arial", 12)).pack(anchor="w", padx=30, pady=(10, 0))
        self.entry_regions = ctk.CTkEntry(main_frame, font=("Arial", 14))
        self.entry_regions.pack(fill="x", padx=30, pady=5)

        # Controls Frame (replaces basic switch)
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.pack(fill="x", padx=30, pady=(15, 5))

        # Slicing Controls
        slice_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        slice_frame.pack(side="left", fill="x", expand=True)

        self.var_coronal = ctk.BooleanVar(value=False)
        self.switch_slice = ctk.CTkSwitch(slice_frame, text="Enable Start Slice", variable=self.var_coronal, font=("Arial", 12))
        self.switch_slice.pack(anchor="w", pady=(0, 5))

        # Coronal Slider (AP axis: 0 to 13200 microns approx)
        ctk.CTkLabel(slice_frame, text="Coronal Depth (AP):", font=("Arial", 12)).pack(anchor="w")
        self.slider_slice = ctk.CTkSlider(slice_frame, from_=0, to=13200, width=250, command=self.on_slider_change)
        self.slider_slice.set(5400) # Default near Bregma
        self.slider_slice.pack(anchor="w")
        self.slider_val_label = ctk.CTkLabel(slice_frame, text="5400 µm", font=("Arial", 10), text_color="gray")
        self.slider_val_label.pack(anchor="w")

        # Coordinates Display Setup (Live feedback area)
        coord_frame = ctk.CTkFrame(controls_frame, fg_color="#1a1a1a", border_color="gray", border_width=1)
        coord_frame.pack(side="right", padx=10)

        ctk.CTkLabel(
            coord_frame,
            text=(
                "Literature estimate (mm; not for surgery)\n"
                f"{DEFAULT_STEREOTAXIC_TRANSFORM.profile_id}"
            ),
            font=("Arial", 11, "bold"),
            text_color="gray",
        ).pack(pady=(2, 0))
        self.coord_label = ctk.CTkLabel(coord_frame, text="AP: -- | ML: -- | DV: --", font=("Consolas", 14, "bold"), text_color="#2CC985")
        self.coord_label.pack(padx=10, pady=5)

        # Launch Button
        self.btn_launch = ctk.CTkButton(main_frame, text="LAUNCH RENDERER", command=self.run_renderer, height=50, width=250, font=("Arial", 16, "bold"), fg_color="#D03B3B", hover_color="#A02B2B")
        self.btn_launch.pack(pady=20)

        # Status Log
        self.status_label = ctk.CTkLabel(main_frame, text="Standby.", text_color="gray", font=("Arial", 12))
        self.status_label.pack(pady=5)

        # Track subprocess
        self.render_process = None

    def on_slider_change(self, value):
        val_int = int(value)
        self.slider_val_label.configure(text=f"{val_int} µm")
        # IPC Communication
        if self.render_process and self.render_process.poll() is None:
            try:
                self.render_process.stdin.write(f"SLICE|{val_int}\n")
                self.render_process.stdin.flush()
            except Exception as e:
                pass # Process might have just died

    def run_renderer(self):
        # Gather selected checkboxes
        selected = [reg for reg, var in self.region_checkboxes.items() if var.get()]

        # Gather custom text
        custom_text = self.entry_regions.get().strip()
        if custom_text:
            custom_list = [r.strip() for r in custom_text.split(",") if r.strip()]
            selected.extend(custom_list)

        if not selected:
            self.status_label.configure(text="Error: Please select or enter at least one region.")
            return

        regions_str = ",".join(selected)
        is_coronal = self.var_coronal.get()

        cmd = [sys.executable, "-u", str(RENDER_SCRIPT), "--regions", regions_str]
        if is_coronal:
            cmd.append("--coronal")

        self.status_label.configure(text=f"Launching BrainRender (Loading might take a moment)...")
        self.btn_launch.configure(state="disabled")

        def task():
            try:
                self.render_process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                    encoding='utf-8',
                    errors='replace'
                )

                # Retrieve output live to prevent blocking if buffer fills and parse coordinates
                while True:
                    line = self.render_process.stdout.readline()
                    if not line and self.render_process.poll() is not None:
                        break
                    if line:
                        stripped = line.strip()
                        # Intercept coordinates from brainrender hover events
                        if stripped.startswith("COORD_ESTIMATE|"):
                            parts = stripped.split("|")
                            if len(parts) == 5:
                                ap, ml, dv = parts[2], parts[3], parts[4]
                                text_val = f"AP: {ap} | ML: {ml} | DV: {dv}"
                                self.after(0, self.coord_label.configure, {"text": text_val})
                        else:
                            print(stripped) # Standard print for other logs

                if self.render_process.returncode == 0:
                    self.after(0, self.status_label.configure, {"text": "Render session closed normally."})
                else:
                    self.after(0, self.status_label.configure, {"text": f"Error. Check console."})
            except Exception as e:
                self.after(0, self.status_label.configure, {"text": f"Exception raised: {e}"})
            finally:
                self.render_process = None
                self.after(0, self.btn_launch.configure, {"state": "normal"})
                self.after(0, self.coord_label.configure, {"text": "AP: -- | ML: -- | DV: --"})

        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        process = self.render_process
        if process and process.poll() is None:
            process.terminate()
        self.destroy()


def main() -> int:
    app = StereotaxicApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
