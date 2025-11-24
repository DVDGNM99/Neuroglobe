import dearpygui.dearpygui as dpg
import sys
import yaml
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.viewer import logic
from src.viewer import rendering

CONFIG_PATH = Path("configs/regions.json")
DEFAULT_ALPHA = 0.8

class ViewerApp:
    def __init__(self):
        self.rows = [] 
        self.mapping = [] 
        self.choices = []
        self.acronym_lookup = {} 
        self.engine = None 
        
        # Variabile per tracciare l'ID del volume 3D corrente
        self.current_tract_id = None
        
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
        
        # Carichiamo i dati con pandas qui per estrarre anche i metadati (tract_id)
        # Nota: logic.process_csv_data torna solo la lista visiva, quindi leggiamo il raw df
        import pandas as pd
        try:
            df = pd.read_csv(file_path)
            # Cerchiamo la colonna magica aggiunta dal Miner
            if 'tract_experiment_id' in df.columns:
                self.current_tract_id = int(df['tract_experiment_id'].iloc[0])
                print(f"[GUI] Found linked tractography ID: {self.current_tract_id}")
                dpg.configure_item("chk_tracts", label=f"Show Tracts (ID: {self.current_tract_id})")
            else:
                self.current_tract_id = None
                dpg.configure_item("chk_tracts", label="Show Tracts (Not Available)")
        except Exception as e:
            print(f"Metadata read error: {e}")
            self.current_tract_id = None

        data = logic.process_csv_data(file_path, colormap_name="plasma")
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

        # --- GESTIONE TRACTOGRAPHY ---
        show_tracts = dpg.get_value("chk_tracts")
        tract_path = None
        
        if show_tracts and self.current_tract_id:
            # Cerchiamo il file .nrrd
            possible_path = self.tracts_dir / f"{self.current_tract_id}.nrrd"
            if possible_path.exists():
                tract_path = possible_path
            else:
                # Fallback per il vecchio formato .mhd (giusto per sicurezza)
                possible_path_mhd = self.tracts_dir / f"{self.current_tract_id}.mhd"
                if possible_path_mhd.exists():
                    tract_path = possible_path_mhd
                else:
                    print(f"[GUI] Warning: Tract file {self.current_tract_id} not found on disk.")

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
            "tracts_enabled": bool(tract_path),
            "tract_id": self.current_tract_id if tract_path else None,
            "targets_rendered": [s['acronym'] for s in selection if s['acronym'] != seed_name],
            "alpha_used": DEFAULT_ALPHA
        }

        dpg.set_value("status_text", "Rendering... Press 'S' to save scene.")
        
        # Lanciamo il render passando il percorso del volume
        engine.render_scene(selection, tract_file=tract_path, alpha=DEFAULT_ALPHA, output_dir=session_save_path, metadata=metadata)
        
        dpg.set_value("status_text", f"Status: Last session saved in scenes/{session_folder_name}")

    def build_gui(self):
        dpg.create_context()
        dpg.create_viewport(title="Neuroglobe Viewer", width=650, height=600)
        
        with dpg.window(tag="Primary Window"):
            dpg.add_text("Neuroglobe Region Selector", color=(0, 200, 255))
            dpg.add_text("Status: Ready", tag="status_text")
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add Region (+)", callback=lambda: self.add_row())
                dpg.add_button(label="LOAD CSV DATA", callback=self.open_csv_dialog)
                dpg.add_spacer(width=20)
                
                # Checkbox ATTIVO ora
                dpg.add_checkbox(tag="chk_tracts", label="Show Tracts (Load CSV first)", default_value=True)
                
                dpg.add_spacer(width=20)
                dpg.add_button(label="RENDER SCENE", callback=self.run_render, width=150)

            dpg.add_separator()
            dpg.add_child_window(tag="rows_container", border=False)
            self.add_row()

        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("Primary Window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()

if __name__ == "__main__":
    app = ViewerApp()
    app.build_gui()