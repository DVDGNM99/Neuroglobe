import customtkinter as ctk
import json
import sys
import subprocess
import threading
import uuid
from pathlib import Path

# --- Constants & Paths ---
BASE_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_PATH.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
MANIFEST_PATH = PROJECT_ROOT / "configs" / "manifest.json"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class GeneticsMinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Neuroglobe Genetics")
        self.geometry("1000x750")

        # --- Config & Data ---
        self.manifest_data = self.load_manifest(MANIFEST_PATH)
        self.genes = self.manifest_data.get("processing", {}).get("genes", [])
        self.regions = self.manifest_data.get("processing", {}).get("target_regions", [])

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Create Tabs
        self.tab_about = self.tab_view.add("About / Workflow")
        self.tab_processor = self.tab_view.add("Genetics Processor")

        # Build Tab Contents
        self.build_about_tab()
        self.build_processor_tab()

    def load_manifest(self, path):
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def log_console(self, msg):
        self.console_out.configure(state="normal")
        self.console_out.insert("end", msg + "\n")
        self.console_out.see("end")
        self.console_out.configure(state="disabled")

    def run_module(self, module_name, extra_args=None, cleanup_path=None):
        self.log_console(f"--- Running {module_name} ---")
        self.set_buttons_state("disabled")
        command = [sys.executable, "-u", "-m", module_name]
        if extra_args:
            command.extend(str(value) for value in extra_args)

        def task():
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(REPOSITORY_ROOT),
                    encoding='utf-8',
                    errors='replace'
                )

                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        self.after(0, self.log_console, line.strip())

                return_code = process.wait()
                if return_code == 0:
                    message = f"--- Finished {module_name} ---"
                else:
                    message = (
                        f"--- {module_name} failed with exit code "
                        f"{return_code} ---"
                    )
                self.after(0, self.log_console, message)

            except Exception as e:
                self.after(0, self.log_console, f"[EXCEPTION] {e}")
            finally:
                if cleanup_path:
                    try:
                        Path(cleanup_path).unlink(missing_ok=True)
                    except OSError as error:
                        self.after(
                            0,
                            self.log_console,
                            f"[WARN] Could not remove runtime state: {error}",
                        )
                self.after(0, lambda: self.set_buttons_state("normal"))

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def run_fetch_and_filter(self):
        # We need to run fetch then filter, doing it in a combined thread
        self.set_buttons_state("disabled")
        def task():
            try:
                # 1. Fetch
                self.after(0, self.log_console, "--- Starting Fetch Phase ---")
                proc1 = subprocess.Popen(
                    [sys.executable, "-u", "-m", "neuroglobe.genetics.miner.fetch_genes"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(REPOSITORY_ROOT), encoding='utf-8', errors='replace'
                )
                for line in proc1.stdout:
                    self.after(0, self.log_console, line.strip())
                fetch_code = proc1.wait()
                if fetch_code != 0:
                    self.after(
                        0,
                        self.log_console,
                        f"[ERROR] Fetch failed with exit code {fetch_code}; filter not started.",
                    )
                    return

                # 2. Filter
                self.after(0, self.log_console, "--- Starting Filter Phase ---")
                proc2 = subprocess.Popen(
                    [sys.executable, "-u", "-m", "neuroglobe.genetics.miner.filter_volume"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=str(REPOSITORY_ROOT), encoding='utf-8', errors='replace'
                )
                for line in proc2.stdout:
                    self.after(0, self.log_console, line.strip())
                filter_code = proc2.wait()
                if filter_code == 0:
                    self.after(0, self.log_console, "--- Pipeline Completed Successfully ---")
                else:
                    self.after(
                        0,
                        self.log_console,
                        f"[ERROR] Filter failed with exit code {filter_code}.",
                    )
            except Exception as e:
                self.after(0, self.log_console, f"[EXCEPTION] Pipeline failed: {e}")
            finally:
                self.after(0, lambda: self.set_buttons_state("normal"))

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def set_buttons_state(self, state):
        btns = [self.btn_fetch_filter, self.btn_viewer]
        for btn in btns:
            if state == "disabled":
                 btn.configure(state="disabled", fg_color="gray")
            else:
                 btn.configure(state="normal")
                 if btn == self.btn_viewer:
                     btn.configure(fg_color="#D03B3B")
                 else:
                     btn.configure(fg_color=["#3a7ebf", "#1f538d"])

    # --- TAB 1: ABOUT ---
    def build_about_tab(self):
        frame = self.tab_about

        title = ctk.CTkLabel(frame, text="Genetics Integration Workflow", font=("Arial", 22, "bold"))
        title.pack(pady=20)

        steps = [
            ("1. Fetch Volumes", "Interrogates Allen API to download grid density data for gene list."),
            ("2. Filter Spatial Data", "Applies CCFv3 brain region masks (PFC, M2, S1, RSP) to erase external data."),
            ("3. Voxel Rendering", "Visualizes the remaining data as distinct Lego-boxes overlaid on the base atlas.")
        ]

        for step, desc in steps:
            step_lbl = ctk.CTkLabel(frame, text=step, font=("Arial", 16, "bold"), text_color="#3B8ED0")
            step_lbl.pack(pady=(15, 0))
            desc_lbl = ctk.CTkLabel(frame, text=desc, font=("Arial", 12))
            desc_lbl.pack(pady=(0, 10))

    # --- TAB 2: PROCESSOR ---
    def build_processor_tab(self):
        frame = self.tab_processor
        frame.grid_columnconfigure(0, weight=3) # Config Side
        frame.grid_columnconfigure(1, weight=2) # Buttons Side

        frame.grid_rowconfigure(0, weight=1) # Main content
        frame.grid_rowconfigure(1, weight=1) # Console (bottom)

        # -- LEFT PANEL (Config) --
        left_panel = ctk.CTkFrame(frame, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Manifest Readout
        ctk.CTkLabel(left_panel, text="Loaded Configurations (manifest.json)", font=("Arial", 16, "bold")).pack(anchor="w", pady=(10, 5))

        ctk.CTkLabel(left_panel, text="Target Genes (Select to render):", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))

        self.gene_checkboxes = {}
        self.gene_scroll = ctk.CTkScrollableFrame(left_panel, height=120, width=350)
        self.gene_scroll.pack(anchor="w", pady=5)
        for g in self.genes:
            var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(self.gene_scroll, text=g, variable=var)
            chk.pack(anchor="w", pady=2, padx=5)
            self.gene_checkboxes[g] = var

        ctk.CTkLabel(left_panel, text="Spatial Filter Areas (Select to render):", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))

        self.region_checkboxes = {}
        self.region_scroll = ctk.CTkScrollableFrame(left_panel, height=80, width=350)
        self.region_scroll.pack(anchor="w", pady=5)
        for r in self.regions:
            var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(self.region_scroll, text=r, variable=var)
            chk.pack(anchor="w", pady=2, padx=5)
            self.region_checkboxes[r] = var

        # -- RIGHT PANEL (Execution) --
        right_panel = ctk.CTkFrame(frame, fg_color="#1A1A1A", corner_radius=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(right_panel, text="Pipeline Execution", font=("Arial", 16, "bold")).pack(pady=15)

        self.btn_fetch_filter = ctk.CTkButton(right_panel, text="1. Fetch & Filter Pipeline", command=self.run_fetch_and_filter, height=50, width=220, font=("Arial", 14, "bold"))
        self.btn_fetch_filter.pack(pady=20)

        self.btn_viewer = ctk.CTkButton(right_panel, text="2. Engage Viewer", command=self.run_viewer, height=60, width=220, font=("Arial", 16, "bold"), fg_color="#D03B3B", hover_color="#A02B2B")
        self.btn_viewer.pack(pady=20)

        # -- BOTTOM PANEL (Console) --
        console_frame = ctk.CTkFrame(frame)
        console_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(console_frame, text="Process Log", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=2)
        self.console_out = ctk.CTkTextbox(console_frame, height=120, font=("Consolas", 12))
        self.console_out.pack(fill="both", expand=True, padx=5, pady=5)
        self.console_out.configure(state="disabled")

    def run_viewer(self):
        # Dump selection state for the rendering script
        state = {
            "selected_genes": [g for g, v in self.gene_checkboxes.items() if v.get()],
            "selected_regions": [r for r, v in self.region_checkboxes.items() if v.get()]
        }
        runtime_dir = PROJECT_ROOT / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        state_path = runtime_dir / f"viewer_{uuid.uuid4().hex}.json"
        temporary_state = state_path.with_suffix(".json.tmp")
        temporary_state.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary_state.replace(state_path)

        self.run_module(
            "neuroglobe.genetics.viewer.controller",
            ["--state", state_path],
            cleanup_path=state_path,
        )

if __name__ == "__main__":
    app = GeneticsMinerApp()
    app.mainloop()
