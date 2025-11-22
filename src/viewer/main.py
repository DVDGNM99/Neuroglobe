import dearpygui.dearpygui as dpg
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.viewer import logic
from src.viewer import rendering

# --- Configuration ---
CONFIG_PATH = Path("configs/regions.json")
DEFAULT_ALPHA = 0.8

class ViewerApp:
    def __init__(self):
        self.rows = [] 
        self.mapping = [] 
        self.choices = []
        self.acronym_lookup = {} 
        self.engine = None 
        self.show_streamlines = False # Checkbox state
        
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.json_file = self.root_dir / CONFIG_PATH
        
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

    # --- FIX QUI SOTTO: Aggiunto parametro is_seed=False ---
    def add_row(self, acronym=None, color_hex=None, is_seed=False):
        """
        Aggiunge una riga alla GUI.
        """
        idx = len(self.rows)
        row_tag = f"row_{idx}"
        
        # Default values (Manual mode)
        def_combo_val = ""
        def_color_rgb = logic.hex_to_rgb(logic.get_preset_hex(idx)) + [255]

        # Override values (CSV mode)
        if acronym and color_hex:
            full_display = self.acronym_lookup.get(acronym, f"{acronym} | Unknown Region")
            
            # Aggiungi etichetta [SEED] se necessario
            if is_seed:
                 full_display = f"[SEED] {full_display}"
                 
            def_combo_val = full_display
            def_color_rgb = logic.hex_to_rgb(color_hex) + [255]

        with dpg.group(horizontal=True, parent="rows_container", tag=row_tag):
            # 1. Combobox
            dpg.add_combo(items=self.choices, width=300, tag=f"{row_tag}_combo", default_value=def_combo_val)
            
            # 2. Color Picker
            dpg.add_color_edit(default_value=def_color_rgb, 
                               tag=f"{row_tag}_color", 
                               no_inputs=True, no_label=True, width=25)

            # 3. Remove Button
            dpg.add_button(label="-", width=20, callback=lambda: self.delete_row(row_tag))

        self.rows.append(row_tag)

    def delete_row(self, tag):
        dpg.delete_item(tag)
        if tag in self.rows:
            self.rows.remove(tag)
            
    def clear_all_rows(self):
        for row in list(self.rows):
            self.delete_row(row)

    # --- CSV Loading Logic ---
    def open_csv_dialog(self):
        with dpg.file_dialog(directory_selector=False, show=True, callback=self.process_csv_selection, width=600, height=400):
            dpg.add_file_extension(".csv", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def process_csv_selection(self, sender, app_data):
        file_path = app_data['file_path_name']
        dpg.set_value("status_text", f"Status: Loading {Path(file_path).name}...")
        
        # 1. Processa dati usando logic.py
        data = logic.process_csv_data(file_path, colormap_name="plasma")
        
        if not data:
            dpg.set_value("status_text", "Error: Could not read CSV or empty data.")
            return

        # 2. Pulisce GUI e popola
        self.clear_all_rows()
        
        limit = 500 
        count = 0
        for item in data:
            if count >= limit:
                print("GUI Limit reached")
                break
            
            # --- FIX QUI SOTTO: Passiamo is_seed alla funzione add_row ---
            self.add_row(acronym=item['acronym'], color_hex=item['color'], is_seed=item.get('is_seed', False))
            count += 1
            
        dpg.set_value("status_text", f"Loaded {count} regions from CSV.")

    def run_render(self):
        engine = self.get_lazy_engine()
        selection = []
        
        for row in self.rows:
            combo_val = dpg.get_value(f"{row}_combo")
            if not combo_val or "|" not in combo_val:
                continue
                
            # Pulizia stringa: Rimuovi "[SEED] " se presente
            clean_val = combo_val.replace("[SEED] ", "")
            acronym = clean_val.split("|")[0].strip()
            
            col_rgba = dpg.get_value(f"{row}_color")
            col_hex = "#{:02x}{:02x}{:02x}".format(int(col_rgba[0]), int(col_rgba[1]), int(col_rgba[2]))
            
            selection.append({"acronym": acronym, "color": col_hex})

        if not selection:
            dpg.set_value("status_text", "Error: No valid regions selected.")
            return

        dpg.set_value("status_text", "Status: Rendering 3D Scene...")
        engine.render_scene(selection, alpha=DEFAULT_ALPHA)
        dpg.set_value("status_text", "Status: Render Complete.")

    def build_gui(self):
        dpg.create_context()
        dpg.create_viewport(title="Neuroglobe Viewer", width=650, height=600)
        
        with dpg.window(tag="Primary Window"):
            dpg.add_text("Neuroglobe Region Selector", color=(0, 200, 255))
            dpg.add_text("Status: Ready", tag="status_text")
            dpg.add_separator()
            
            # Control Group
            with dpg.group(horizontal=True):
                dpg.add_button(label="Add Region (+)", callback=lambda: self.add_row())
                dpg.add_button(label="LOAD CSV DATA", callback=self.open_csv_dialog)
                dpg.add_spacer(width=20)
                
                # Checkbox placeholder per il futuro
                dpg.add_checkbox(label="Show Tracts (Future)", default_value=False, 
                                 callback=lambda s, a: print("Streamlines coming in Phase 3"))
                
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