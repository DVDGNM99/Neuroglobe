import dearpygui.dearpygui as dpg
import sys
import yaml
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.viewer import logic
from src.viewer import rendering
from src.viewer import filter_tracts

CONFIG_PATH = Path("configs/regions.json")
DEFAULT_ALPHA = 0.8

class ViewerApp:
    def __init__(self):
        self.rows = [] 
        self.mapping = [] 
        self.choices = []
        self.acronym_lookup = {} 
        self.engine = None 
        
        # Variable to track the current 3D volume ID
        self.current_tract_id = None
        self.current_scalar_min = 0.0
        self.current_scalar_max = 1.0
        
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.json_file = self.root_dir / CONFIG_PATH
        self.scenes_dir = self.root_dir / "scenes"
        self.tracts_dir = self.root_dir / "data" / "processed" / "tracts"
        
        self.load_data()

    def load_data(self):
        print(f"Loading config from: {self.json_file}")
        self.mapping = logic.load_regions_config(str(self.json_file))
        self.choices = [x.display for x in self.mapping]
        self.acronym_lookup = {x.acronym: x.display for x in self.mapping}

    def get_lazy_engine(self):
        if self.engine is None:
            dpg.set_value("status_text", "Status: Loading Atlas... (Wait)")
            self.engine = rendering.RenderEngine()
            dpg.set_value("status_text", "Status: Atlas Loaded.")
        return self.engine

    def add_row(self, acronym=None, color_hex=None, is_seed=False):
        idx = len(self.rows)
        row_tag = f"row_{idx}"
        
        def_combo_val = ""
        def_color_rgb = logic.hex_to_rgb(logic.get_preset_hex(idx)) + [255]

        if acronym and color_hex:
            full_display = self.acronym_lookup.get(acronym, f"{acronym} | Unknown Region")
            if is_seed: full_display = f"[SEED] {full_display}"
            def_combo_val = full_display
            def_color_rgb = logic.hex_to_rgb(color_hex) + [255]

        with dpg.group(horizontal=True, parent="rows_container", tag=row_tag):
            dpg.add_combo(items=self.choices, width=300, tag=f"{row_tag}_combo", default_value=def_combo_val)
            dpg.add_color_edit(default_value=def_color_rgb, tag=f"{row_tag}_color", no_inputs=True, no_label=True, width=25)
            dpg.add_button(label="-", width=20, callback=lambda: self.delete_row(row_tag))
        self.rows.append(row_tag)

    def delete_row(self, tag):
        dpg.delete_item(tag)
        if tag in self.rows: self.rows.remove(tag)
            
    def clear_all_rows(self):
        for row in list(self.rows): self.delete_row(row)

    def open_csv_dialog(self):
        with dpg.file_dialog(directory_selector=False, show=True, callback=self.process_csv_selection, width=600, height=400):
            dpg.add_file_extension(".csv", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def process_csv_selection(self, sender, app_data):
        file_path = app_data['file_path_name']
        dpg.set_value("status_text", f"Status: Loading {Path(file_path).name}...")
        
        # Load data with pandas here to extract metadata (tract_id)
        # Note: logic.process_csv_data returns only the visual list, so we read the raw df
        import pandas as pd
        try:
            df = pd.read_csv(file_path)
            # Look for the magic column added by the Miner
            if 'tract_experiment_id' in df.columns:
                self.current_tract_id = int(df['tract_experiment_id'].iloc[0])
                print(f"[GUI] Found linked tractography ID: {self.current_tract_id}")
                dpg.configure_item("combo_viz_mode", label=f"Viz Mode (ID: {self.current_tract_id})")
            else:
                self.current_tract_id = None
                dpg.configure_item("combo_viz_mode", label="Viz Mode (No ID)")
        except Exception as e:
            print(f"Metadata read error: {e}")
            self.current_tract_id = None

        data, v_min, v_max = logic.process_csv_data(file_path, colormap_name="viridis")
        
        # Store metadata for rendering
        self.current_scalar_min = v_min
        self.current_scalar_max = v_max
        if not data:
            dpg.set_value("status_text", "Error: Could not read CSV or empty data.")
            return
            
        self.clear_all_rows()
        limit = 500 
        count = 0
        for item in data:
            if count >= limit: break
            self.add_row(acronym=item['acronym'], color_hex=item['color'], is_seed=item.get('is_seed', False))
            count += 1
        dpg.set_value("status_text", f"Loaded {count} regions from CSV.")

    def get_current_seed_info(self):
        seed_acronym = "ManualSelection"
        found_seed = False
        for row in self.rows:
            combo_val = dpg.get_value(f"{row}_combo")
            if combo_val and "[SEED]" in combo_val:
                seed_acronym = combo_val.replace("[SEED] ", "").split("|")[0].strip()
                found_seed = True
                break
        return seed_acronym, found_seed

    def open_group_dialog(self):
        with dpg.window(label="Add Region Group", modal=True, show=True, tag="group_dialog", width=300, height=150):
            dpg.add_text("Enter Parent Acronym (e.g. Isocortex):")
            dpg.add_input_text(tag="input_parent_acronym", default_value="Isocortex")
            dpg.add_button(label="Add Descendants", callback=self.process_group_addition, width=200)
            dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("group_dialog"))

    def process_group_addition(self):
        parent = dpg.get_value("input_parent_acronym").strip()
        dpg.delete_item("group_dialog")
        
        if not parent: return
        
        dpg.set_value("status_text", f"Status: Fetching descendants for {parent}...")
        print(f"[GUI] Fetching descendants for {parent}...")
        
        # Call logic
        descendants = logic.get_descendants(parent)
        
        if not descendants:
            dpg.set_value("status_text", f"Error: No descendants found for {parent}.")
            return
            
        # Add them to the list
        count = 0
        for acr in descendants:
            # Only add if we have it in our mapping (i.e., it exists in the atlas config we loaded)
            # Or we can just try to add it and if it's not in the combo it might be weird
            if acr in self.acronym_lookup:
                self.add_row(acronym=acr, color_hex="#CCCCCC") # Default gray for group add
                count += 1
        
        dpg.set_value("status_text", f"Status: Added {count} regions from group {parent}.")
        print(f"[GUI] Added {count} regions.")

    def scan_csv_files(self):
        """Scans data/processed for CSV files."""
        csv_dir = self.root_dir / "data" / "processed"
        if not csv_dir.exists(): return []
        return [f.name for f in csv_dir.glob("*.csv")]

    def process_manual_action(self, sender, app_data):
        action = app_data
        if action == "Add Region (+)":
            self.add_row()
        elif action == "Add Group (+)":
            self.open_group_dialog()
        elif action == "Filter Tracts":
            self.run_filter_callback()
        
        # Reset combo
        dpg.set_value("combo_manual", "Select Action...")

    def load_csv_from_combo(self, sender, app_data):
        filename = app_data
        if not filename or filename == "Load CSV Data...": return
        
        file_path = self.root_dir / "data" / "processed" / filename
        if file_path.exists():
            # Reuse the existing logic, just wrapping the path
            # We construct a fake app_data dict to reuse process_csv_selection or just call logic directly
            # Let's refactor process_csv_selection to be cleaner, but for now just call it manually
            self.process_csv_selection(None, {'file_path_name': str(file_path)})
        else:
            dpg.set_value("status_text", f"Error: File not found {filename}")

    def build_gui(self):
        dpg.create_context()
        dpg.create_viewport(title="Neuroglobe Viewer", width=700, height=650)
        
        with dpg.window(tag="Primary Window"):
            dpg.add_text("Neuroglobe Viewer", color=(0, 200, 255))
            dpg.add_text("Status: Ready", tag="status_text")
            dpg.add_separator()

            # --- TOP BAR ---
            with dpg.group(horizontal=True):
                # Manual Actions
                dpg.add_text("Manual:")
                dpg.add_combo(items=["Add Region (+)", "Add Group (+)", "Filter Tracts"], 
                              default_value="Select Action...", width=200, 
                              callback=self.process_manual_action, tag="combo_manual")
                
                dpg.add_spacer(width=20)
                
                # Load Data
                csv_files = self.scan_csv_files()
                dpg.add_text("Load Data:")
                dpg.add_combo(items=csv_files, default_value="Select CSV...", width=250, 
                              callback=self.load_csv_from_combo, tag="combo_csv")

            dpg.add_separator()

            # --- MIDDLE (Rows) ---
            # Use a child window that stretches but leaves room for bottom bar
            # height=-60 leaves 60px at the bottom
            with dpg.child_window(tag="rows_container", border=False, height=-60):
                self.add_row()

            # --- BOTTOM BAR ---
            dpg.add_separator()
            with dpg.group(horizontal=True):
                # Render Button (Large)
                dpg.add_button(label="RENDER SCENE", callback=self.run_render, width=200, height=40)
                
                dpg.add_spacer(width=20)
                
                # Viz Mode (Large)
                dpg.add_text("Viz Mode:")
                dpg.add_combo(items=["None", "Density (Raw)", "Density (Filtered)", "Streamlines (Tubes)"], 
                              tag="combo_viz_mode", default_value="Density (Raw)", width=250)

        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("Primary Window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()

    def run_filter_callback(self):
        if not self.current_tract_id:
            dpg.set_value("status_text", "Error: No tractography ID loaded (Load CSV first).")
            return

        # metric = dpg.get_value("radio_metric").lower() # density or energy
        metric = "density" # Hardcoded for now
        
        # Construct path to raw NRRD
        # Expecting {id}_density.nrrd or {id}_energy.nrrd
        raw_filename = f"{self.current_tract_id}_{metric}.nrrd"
        raw_path = self.tracts_dir / raw_filename
        
        # Fallback for legacy files (just ID.nrrd -> assume density)
        if not raw_path.exists() and metric == "density":
             legacy_path = self.tracts_dir / f"{self.current_tract_id}.nrrd"
             if legacy_path.exists():
                 raw_path = legacy_path
                 print(f"[GUI] Using legacy density file: {raw_path.name}")

        if not raw_path.exists():
             dpg.set_value("status_text", f"Error: Raw file not found: {raw_path.name}")
             return

        dpg.set_value("status_text", f"Status: Filtering {metric.capitalize()}... (Please Wait)")
        print(f"[GUI] Starting Filter Process for {metric}...")
        
        # Output specific to metric
        output_filename = f"filtered_{metric}.vtk"
        output_path = self.tracts_dir / output_filename

        try:
            output = filter_tracts.run_filter(input_path=raw_path, output_path=output_path)
            if output and output.exists():
                dpg.set_value("status_text", f"Status: Filtered {metric} ready!")
                dpg.set_value("combo_viz_mode", "Density (Filtered)")
                print(f"[GUI] Filter success: {output}")
            else:
                dpg.set_value("status_text", "Error: Filtering failed (check console).")
        except Exception as e:
             dpg.set_value("status_text", f"Error during filtering: {e}")
             print(f"[GUI] Exception: {e}")

    def run_render(self):
        engine = self.get_lazy_engine()
        selection = []
        for row in self.rows:
            combo_val = dpg.get_value(f"{row}_combo")
            if not combo_val or "|" not in combo_val: continue
            clean_val = combo_val.replace("[SEED] ", "")
            acronym = clean_val.split("|")[0].strip()
            col_rgba = dpg.get_value(f"{row}_color")
            col_hex = "#{:02x}{:02x}{:02x}".format(int(col_rgba[0]), int(col_rgba[1]), int(col_rgba[2]))
            selection.append({"acronym": acronym, "color": col_hex})

        if not selection:
            dpg.set_value("status_text", "Error: No valid regions selected.")
            return

        # --- TRACTOGRAPHY MANAGEMENT (STRICT MODES) ---
        viz_mode = dpg.get_value("combo_viz_mode")
        metric = "density" # Hardcoded for now
        tract_path = None
        
        if viz_mode == "None":
            tract_path = None
            print("[GUI] Viz Mode: None (Tracts hidden)")

        elif viz_mode == "Density (Raw)":
            # 1. Check for FIXED metadata file (Native Workflow)
            # Now using .vtk (Mesh) to ensure consistency with Filtered mode
            fixed_path = self.tracts_dir / f"{self.current_tract_id}_{metric}_fixed.vtk"
            
            # 2. Fallback to Raw NRRD
            raw_path = self.tracts_dir / f"{self.current_tract_id}_{metric}.nrrd"
            
            # 3. Legacy fallback
            legacy_path = self.tracts_dir / f"{self.current_tract_id}.nrrd"

            if fixed_path.exists():
                tract_path = fixed_path
                print(f"[GUI] Using FIXED {metric} (Mesh): {fixed_path.name}")
            elif raw_path.exists():
                tract_path = raw_path
                print(f"[GUI] Using RAW {metric}: {raw_path.name}")
            elif legacy_path.exists() and metric == "density":
                tract_path = legacy_path
                print(f"[GUI] Using LEGACY {metric}: {legacy_path.name}")
            else:
                print(f"[GUI] Raw file not found: {raw_path.name}")
                dpg.set_value("status_text", "Error: Raw density file not found.")

        elif viz_mode == "Density (Filtered)":
            # Force Filtered VTK
            filtered_path = self.tracts_dir / f"filtered_{metric}.vtk"
            if filtered_path.exists():
                tract_path = filtered_path
                print(f"[GUI] Using FILTERED {metric}: {filtered_path.name}")
            else:
                print(f"[GUI] Filtered file not found. Run 'Filter Tracts' first.")
                dpg.set_value("status_text", "Error: No filtered data. Click 'Filter Tracts' first.")

        elif viz_mode == "Streamlines (Tubes)":
            # Look for streamlines JSON
            if self.current_tract_id:
                stream_path = self.tracts_dir / f"{self.current_tract_id}_streamlines.json"
                if stream_path.exists():
                    tract_path = stream_path
                    print(f"[GUI] Found Streamlines: {stream_path.name}")
                else:
                    print(f"[GUI] Streamlines file not found: {stream_path.name}")
                    dpg.set_value("status_text", "Warning: No streamlines data found for this ID.")

        seed_name, is_csv_seed = self.get_current_seed_info()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_folder_name = f"{seed_name}_{timestamp}"
        session_save_path = self.scenes_dir / session_folder_name
        
        try:
            session_save_path.mkdir(parents=True, exist_ok=True)
            print(f"\n[SYSTEM] Save Folder Created: {session_save_path.absolute()}")
        except Exception as e:
            dpg.set_value("status_text", f"Error creating save folder: {e}")
            return

        metadata = {
            "experiment_seed": seed_name,
            "timestamp": timestamp,
            "source_type": "CSV Loaded" if is_csv_seed else "Manual Selection",
            "regions_count": len(selection),
            "tracts_enabled": (viz_mode != "None"),
            "tract_file_used": tract_path.name if tract_path else "None",
            "metric_used": metric,
            "viz_mode": viz_mode,
            "targets_rendered": [s['acronym'] for s in selection if s['acronym'] != seed_name],
            "targets_rendered": [s['acronym'] for s in selection if s['acronym'] != seed_name],
            "alpha_used": DEFAULT_ALPHA,
            "scalar_min": self.current_scalar_min,
            "scalar_max": self.current_scalar_max
        }

        dpg.set_value("status_text", "Rendering... Press 'S' to save scene.")
        
        # Rendering call
        engine.render_scene(selection, tract_file=tract_path, alpha=DEFAULT_ALPHA, output_dir=session_save_path, metadata=metadata, visualization_mode=viz_mode)
        
        dpg.set_value("status_text", f"Status: Last session saved in scenes/{session_folder_name}")

if __name__ == "__main__":
    app = ViewerApp()
    app.build_gui()