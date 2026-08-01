import customtkinter as ctk
import yaml
import sys
import json
from pathlib import Path
import tkinter as tk
import threading

from neuroglobe.core.jobs import CancellationToken, JobProgress, run_streaming_job
from neuroglobe.projections.config import MINING_METRICS

# --- Constants & Paths ---
BASE_PATH = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_PATH.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "mining_config.yaml"
REGIONS_PATH = PROJECT_ROOT / "configs" / "regions.json"
JOB_TIMEOUT_SECONDS = 2 * 60 * 60

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SmartSearchComboBox(ctk.CTkComboBox):
    def __init__(self, master, all_values, **kwargs):
        # Limit initial values to 100 to prevent rendering lag
        initial_values = all_values[:100] if len(all_values) > 100 else all_values
        super().__init__(master, values=initial_values, **kwargs)
        self.all_values = all_values
        self._entry.bind("<KeyRelease>", self.filter_values)
    
    def filter_values(self, event):
        curr_text = self._entry.get().lower()
        if curr_text == "":
            # Restore default list (limited)
            self.configure(values=self.all_values[:100])
        else:
            filtered = [v for v in self.all_values if v.lower().startswith(curr_text)]
            # Limit suggestions to top 50
            self.configure(values=filtered[:50])

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Neuroglobe Miner")
        self.geometry("1000x750")
        
        # --- Config & Data ---
        self.config_data = self.load_yaml(CONFIG_PATH)
        self.regions_list = self.load_regions(REGIONS_PATH)
        print(f"[DEBUG] Loaded {len(self.regions_list)} regions.")
        
        # Internal State
        # Load targets from config
        self.current_targets = self.config_data.get("selection", {}).get("custom_targets", [])
        self.active_job: CancellationToken | None = None
        
        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Create Tabs
        self.tab_about = self.tab_view.add("About / Workflow")
        self.tab_processor = self.tab_view.add("Mining Processor")
        self.tab_analysis = self.tab_view.add("Miner Analysis")

        # Build Tab Contents
        self.build_about_tab()
        self.build_processor_tab()
        self.build_analysis_tab()

    def load_yaml(self, path):
        if path.exists():
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def save_config(self):
        if self.save_config_silent():
            print("[GUI] Configuration Saved Successfully.")
            self.log_console("[SUCCESS] Configuration saved to mining_config.yaml")

    def save_config_silent(self):
        # Update config data from UI state
        # 1. Seed
        seed_val = self.combo_seed.get()
        if seed_val:
            # Strict Validation
            if seed_val not in self.regions_list:
                self.log_console(f"[ERROR] Seed '{seed_val}' is NOT a valid region.")
                self.log_console("[INFO] Save Aborted. Please correct the Seed.")
                return False

            if "experiment" not in self.config_data: self.config_data["experiment"] = {}
            self.config_data["experiment"]["seed_acronym"] = seed_val
        
        # 2. Targets
        if "selection" not in self.config_data: self.config_data["selection"] = {}
        self.config_data["selection"]["custom_targets"] = self.current_targets
        self.config_data["selection"]["use_custom_targets"] = True # Force True if saving from GUI
        
        # 3. Metric
        raw_metric = self.opt_metric.get()
        metric_val = raw_metric
        
        if "processing" not in self.config_data: self.config_data["processing"] = {}
        self.config_data["processing"]["metric"] = metric_val
        
        # Save to file
        try:
            with open(CONFIG_PATH, 'w') as f:
                yaml.dump(self.config_data, f, default_flow_style=False)
            return True
        except Exception as e:
            self.log_console(f"[ERROR] Failed to save config: {e}")
            return False

    # ... (load_regions is already fixed in previous step, skipping to opt_metric update in build_processor_tab) ...

    # We need to target the build_processor_tab method to update the values tuple


    def load_regions(self, path):
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f) 
                    # Data is dict: {"ACRONYM": "Name", ...}
                    if isinstance(data, dict):
                        return sorted(list(data.keys()))
                    elif isinstance(data, list):
                        # Fallback if format changes
                        return sorted([r.get('acronym', '') for r in data if isinstance(r, dict)])
            except Exception as e:
                print(f"[ERROR] Error loading regions: {e}")
        return []

    def update_target_display(self):
        self.textbox_targets.configure(state="normal")
        self.textbox_targets.delete("0.0", "end")
        
        for t in self.current_targets:
            self.textbox_targets.insert("end", f"• {t}\n")
            
        self.textbox_targets.configure(state="disabled")

    def add_target(self):
        val = self.combo_target_add.get()
        
        # Validation
        if not val:
            return
            
        if val not in self.regions_list:
            self.log_console(f"[ERROR] '{val}' is NOT a valid region acronym.")
            return

        if val not in self.current_targets:
            self.current_targets.append(val)
            self.update_target_display()
            self.log_console(f"Added target: {val}")
        else:
            self.log_console(f"[INFO] Target '{val}' already in list.")

    def remove_target(self):
        val = self.combo_target_add.get()
        if val in self.current_targets:
            self.current_targets.remove(val)
            self.update_target_display()
            self.log_console(f"Removed target: {val}")
        else:
            self.log_console(f"[WARNING] Target '{val}' not in list. Type exact name to remove.")

    def log_console(self, msg):
        self.console_out.configure(state="normal")
        self.console_out.insert("end", msg + "\n")
        self.console_out.see("end")
        self.console_out.configure(state="disabled")

    # --- TAB 1: ABOUT ---
    def build_about_tab(self):
        frame = self.tab_about
        
        title = ctk.CTkLabel(frame, text="Mining Pipeline Workflow", font=("Arial", 22, "bold"))
        title.pack(pady=20)
        
        steps = [
            ("1. Fetch Experiments", "Queries the Allen API to find experiments for your Seed."),
            ("2. Extract Tracts", "Downloads 3D volumetric data for the best representative experiment."),
            ("3. Aggregate & Build", "Combines data from multiple experiments to create a mean model."),
            ("4. Filter Targets", "Refines the extensive dataset to only show selected targets.")
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
        
        # 1. Seed
        ctk.CTkLabel(left_panel, text="Seed Region (Injection)", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 5))
        self.combo_seed = SmartSearchComboBox(left_panel, self.regions_list, width=300)
        self.combo_seed.pack(anchor="w", pady=5)
        
        # Set current seed
        curr_seed = self.config_data.get("experiment", {}).get("seed_acronym", "")
        self.combo_seed.set(curr_seed)

        # 2. Targets Helper (Add/Remove)
        ctk.CTkLabel(left_panel, text="Manage Targets", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5))
        
        mgmt_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        mgmt_frame.pack(anchor="w", fill="x")
        
        self.combo_target_add = SmartSearchComboBox(mgmt_frame, self.regions_list, width=200)
        self.combo_target_add.pack(side="left", padx=(0, 10))
        
        btn_add = ctk.CTkButton(mgmt_frame, text="+", width=40, command=self.add_target, fg_color="#2CC985")
        btn_add.pack(side="left", padx=5)
        
        btn_remove = ctk.CTkButton(mgmt_frame, text="-", width=40, command=self.remove_target, fg_color="#C92C2C")
        btn_remove.pack(side="left", padx=5)

        # 3. Target List Display
        ctk.CTkLabel(left_panel, text="Selected Targets List:", font=("Arial", 12)).pack(anchor="w", pady=(10, 0))
        self.textbox_targets = ctk.CTkTextbox(left_panel, height=150, width=400)
        self.textbox_targets.pack(anchor="w", pady=5)
        self.update_target_display()

        # 4. Metric
        ctk.CTkLabel(left_panel, text="Aggregation Metric", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5))
        self.opt_metric = ctk.CTkOptionMenu(
            left_panel,
            values=list(MINING_METRICS),
        )
        self.opt_metric.pack(anchor="w", pady=5)
        
        if "processing" in self.config_data and "metric" in self.config_data["processing"]:
             self.opt_metric.set(self.config_data["processing"]["metric"])
        
        # 5. Save Button
        btn_save = ctk.CTkButton(left_panel, text="SAVE CONFIGURATION", command=self.save_config, height=40, fg_color="#2B2B2B", hover_color="#404040", border_width=1, border_color="gray")
        btn_save.pack(anchor="w", pady=30, fill="x")

        # -- RIGHT PANEL (Execution) --
        right_panel = ctk.CTkFrame(frame, fg_color="#1A1A1A", corner_radius=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(right_panel, text="Pipeline Execution", font=("Arial", 16, "bold")).pack(pady=15)
        
        # Action Buttons Connected to Scripts
        # 1. Fetch
        self.btn_fetch = ctk.CTkButton(right_panel, text="1. Fetch Experiments", command=lambda: self.run_script("fetch.py"), height=45, width=220, font=("Arial", 14))
        self.btn_fetch.pack(pady=10)

        # 2. Extract
        self.btn_extract = ctk.CTkButton(right_panel, text="2. Extract Tracts", command=lambda: self.run_script("extract_tracts.py"), height=45, width=220, font=("Arial", 14))
        self.btn_extract.pack(pady=10)

        # 3. Aggregate
        self.btn_aggregate = ctk.CTkButton(right_panel, text="3. Aggregate & Build", command=lambda: self.run_script("aggregate.py"), height=45, width=220, font=("Arial", 14), fg_color="#2C85C9")
        self.btn_aggregate.pack(pady=10)

        # 4. Filter
        self.btn_filter = ctk.CTkButton(right_panel, text="4. Filter Targets", command=lambda: self.run_script("filter_csv.py"), height=45, width=220, font=("Arial", 14))
        self.btn_filter.pack(pady=10)

        self.btn_cancel = ctk.CTkButton(
            right_panel,
            text="Cancel active job",
            command=self.cancel_active_job,
            height=35,
            width=220,
            state="disabled",
            fg_color="#8B2E2E",
        )
        self.btn_cancel.pack(pady=(18, 6))
        self.job_status = ctk.CTkLabel(right_panel, text="Idle", text_color="gray")
        self.job_status.pack(pady=(0, 10))

        # -- BOTTOM PANEL (Console) --
        console_frame = ctk.CTkFrame(frame)
        console_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(console_frame, text="Process Log", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=2)
        self.console_out = ctk.CTkTextbox(console_frame, height=100, font=("Consolas", 12))
        self.console_out.pack(fill="both", expand=True, padx=5, pady=5)
        self.console_out.configure(state="disabled")

    # --- TAB 3: ANALYSIS ---
    def build_analysis_tab(self):
        frame = self.tab_analysis
        
        frame.grid_rowconfigure(0, weight=1) # Main content
        frame.grid_rowconfigure(1, weight=1) # Console
        frame.grid_columnconfigure(0, weight=1)

        center_box = ctk.CTkFrame(frame, fg_color="transparent")
        center_box.grid(row=0, column=0, sticky="nsew")
        center_box.pack_propagate(False) # Let grid handle size? No, just center it.
        # Actually easier to just pack center box if we want centering, but we need row 1 for console.
        # Let's simple grid:
        
        lbl = ctk.CTkLabel(center_box, text="Miner Analysis Module", font=("Arial", 24, "bold"))
        lbl.pack(pady=(40, 20))
        
        desc = ctk.CTkLabel(center_box, text="Extract raw data (CSV) for all experiments without aggregation.\nUseful for statistical analysis (ANOVA, etc.)", justify="center")
        desc.pack(pady=10)
        
        self.btn_analysis = ctk.CTkButton(center_box, text="RUN FULL ANALYSIS", command=lambda: self.run_script("miner_analysis.py", self.console_analysis), height=60, width=300, font=("Arial", 16, "bold"), fg_color="#D03B3B", hover_color="#A02B2B")
        self.btn_analysis.pack(pady=40)

        # Console for Analysis
        console_frame = ctk.CTkFrame(frame)
        console_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(console_frame, text="Analysis Log", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=2)
        self.console_analysis = ctk.CTkTextbox(console_frame, height=150, font=("Consolas", 12))
        self.console_analysis.pack(fill="both", expand=True, padx=5, pady=5)
        self.console_analysis.configure(state="disabled")

    def set_buttons_state(self, state):
        """Disables/Enables all execution buttons to prevent concurrent runs."""
        btns = [
            getattr(self, 'btn_fetch', None),
            getattr(self, 'btn_extract', None),
            getattr(self, 'btn_aggregate', None),
            getattr(self, 'btn_filter', None),
            getattr(self, 'btn_analysis', None)
        ]
        for btn in btns:
            if btn:
                if state == "disabled":
                     btn.configure(state="disabled", fg_color="gray")
                else:
                     btn.configure(state="normal")
                     if btn == getattr(self, 'btn_aggregate', None):
                         btn.configure(fg_color="#2C85C9") # Blue
                     elif btn == getattr(self, 'btn_analysis', None):
                         btn.configure(fg_color="#D03B3B") # Red
                     else:
                         btn.configure(fg_color=["#3a7ebf", "#1f538d"])
        cancel_button = getattr(self, "btn_cancel", None)
        if cancel_button is not None:
            cancel_button.configure(state="normal" if state == "disabled" else "disabled")

    def update_job_progress(self, progress: JobProgress):
        self.job_status.configure(
            text=(
                f"PID {progress.process_id} · {progress.elapsed_seconds:.1f}s · "
                f"{progress.lines_emitted} log lines"
            )
        )

    def cancel_active_job(self):
        if self.active_job is not None:
            self.active_job.cancel()
            self.log_console("[GUI] Cancellation requested; waiting for process shutdown...")

    def log_to_widget(self, widget, msg):
        if widget:
            widget.configure(state="normal")
            widget.insert("end", msg + "\n")
            widget.see("end")
            widget.configure(state="disabled")

    def log_console(self, msg):
        # Legacy support for helper methods that might call this
        self.log_to_widget(self.console_out, msg)

    def run_script(self, script_name, output_widget=None):
        # Default to main console if none provided
        if output_widget is None:
            output_widget = self.console_out
        if self.active_job is not None:
            self.log_to_widget(output_widget, "[ERROR] Another job is already running.")
            return

        # Auto-Save before running to prevent data mismatch
        print(f"[GUI] Auto-saving before running {script_name}...")
        
        # Log to the specific widget
        self.log_to_widget(output_widget, f"[GUI] Auto-saving configuration...")
        
        success = self.save_config_silent()
        if not success:
            self.log_to_widget(output_widget, "[ERROR] Aborting run due to invalid configuration.")
            return

        module_name = (
            "neuroglobe.projections.miner."
            + Path(script_name).stem
        )
        
        self.log_to_widget(output_widget, f"--- Running {script_name} ---")
        self.set_buttons_state("disabled") # LOCK UI
        token = CancellationToken()
        self.active_job = token

        def task():
            try:
                result = run_streaming_job(
                    [sys.executable, "-u", "-m", module_name],
                    cwd=REPOSITORY_ROOT,
                    on_output=lambda line: self.after(
                        0, self.log_to_widget, output_widget, line
                    ),
                    timeout_seconds=JOB_TIMEOUT_SECONDS,
                    cancellation_token=token,
                    on_progress=lambda progress: self.after(
                        0, self.update_job_progress, progress
                    ),
                )
                if result.cancelled:
                    message = f"--- Cancelled {script_name} ---"
                elif result.timed_out:
                    message = f"--- {script_name} timed out ---"
                elif result.succeeded:
                    message = f"--- Finished {script_name} ---"
                else:
                    message = (
                        f"--- {script_name} failed with exit code "
                        f"{result.returncode} ---"
                    )
                self.after(0, self.log_to_widget, output_widget, message)
            except Exception as e:
                self.after(0, self.log_to_widget, output_widget, f"[EXCEPTION] {e}")
            finally:
                # UNLOCK UI ALWAYS
                self.active_job = None
                self.after(0, self.job_status.configure, {"text": "Idle"})
                self.after(0, lambda: self.set_buttons_state("normal"))

        t = threading.Thread(target=task, daemon=True)
        t.start()

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()

