import dearpygui.dearpygui as dpg
from pathlib import Path
from src.viewer import logic

class ViewerGUI:
    def __init__(self, controller):
        self.controller = controller
        self.rows = [] 
        
    def add_row(self, acronym=None, color_hex=None, is_seed=False):
        idx = len(self.rows)
        row_tag = f"row_{idx}"
        
        def_combo_val = ""
        def_color_rgb = logic.hex_to_rgb(logic.get_preset_hex(idx)) + [255]

        if acronym and color_hex:
            full_display = self.controller.acronym_lookup.get(acronym, f"{acronym} | Unknown Region")
            if is_seed: full_display = f"[SEED] {full_display}"
            def_combo_val = full_display
            def_color_rgb = logic.hex_to_rgb(color_hex) + [255]

        with dpg.group(horizontal=True, parent="rows_container", tag=row_tag):
            dpg.add_combo(items=self.controller.choices, width=300, tag=f"{row_tag}_combo", default_value=def_combo_val)
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
        
        # 1. Load Metadata via Controller
        tract_id = self.controller.load_csv_metadata(file_path)
        if tract_id:
            dpg.configure_item("combo_viz_mode", label=f"Viz Mode (ID: {tract_id})")
        else:
            dpg.configure_item("combo_viz_mode", label="Viz Mode (No ID)")

        # 2. Load Data via Controller
        data = self.controller.process_csv_data(file_path)
        
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
        
        descendants = self.controller.get_descendants(parent)
        
        if not descendants:
            dpg.set_value("status_text", f"Error: No descendants found for {parent}.")
            return
            
        count = 0
        for acr in descendants:
            if acr in self.controller.acronym_lookup:
                self.add_row(acronym=acr, color_hex="#CCCCCC") 
                count += 1
        
        dpg.set_value("status_text", f"Status: Added {count} regions from group {parent}.")

    def process_manual_action(self, sender, app_data):
        action = app_data
        if action == "Add Region (+)":
            self.add_row()
        elif action == "Add Group (+)":
            self.open_group_dialog()
        elif action == "Filter Tracts":
            self.run_filter_callback()
        
        dpg.set_value("combo_manual", "Select Action...")

    def load_csv_from_combo(self, sender, app_data):
        filename = app_data
        if not filename or filename == "Load CSV Data...": return
        
        file_path = self.controller.root_dir / "data" / "processed" / filename
        if file_path.exists():
            self.process_csv_selection(None, {'file_path_name': str(file_path)})
        else:
            dpg.set_value("status_text", f"Error: File not found {filename}")

    def run_filter_callback(self):
        success, message = self.controller.filter_tracts(
            metric="density", 
            status_callback=lambda msg: dpg.set_value("status_text", msg)
        )
        dpg.set_value("status_text", message)
        if success:
            dpg.set_value("combo_viz_mode", "Density (Filtered)")

    def run_render(self):
        selection = []
        for row in self.rows:
            combo_val = dpg.get_value(f"{row}_combo")
            if not combo_val or "|" not in combo_val: continue
            clean_val = combo_val.replace("[SEED] ", "")
            acronym = clean_val.split("|")[0].strip()
            col_rgba = dpg.get_value(f"{row}_color")
            col_hex = "#{:02x}{:02x}{:02x}".format(int(col_rgba[0]), int(col_rgba[1]), int(col_rgba[2]))
            selection.append({"acronym": acronym, "color": col_hex})

        viz_mode = dpg.get_value("combo_viz_mode")
        seed_name, is_csv_seed = self.get_current_seed_info()
        show_legend = dpg.get_value("chk_legend")

        success, message = self.controller.render_scene(
            selection, 
            viz_mode, 
            seed_name, 
            is_csv_seed, 
            show_legend=show_legend,
            status_callback=lambda msg: dpg.set_value("status_text", msg)
        )
        dpg.set_value("status_text", message)

    def build(self):
        dpg.create_context()
        dpg.create_viewport(title="Neuroglobe Viewer", width=700, height=650)
        
        with dpg.window(tag="Primary Window"):
            dpg.add_text("Neuroglobe Viewer", color=(0, 200, 255))
            dpg.add_text("Status: Ready", tag="status_text")
            dpg.add_separator()

            # --- TOP BAR ---
            with dpg.group(horizontal=True):
                dpg.add_text("Manual:")
                dpg.add_combo(items=["Add Region (+)", "Add Group (+)", "Filter Tracts"], 
                              default_value="Select Action...", width=200, 
                              callback=self.process_manual_action, tag="combo_manual")
                
                dpg.add_spacer(width=20)
                
                csv_files = self.controller.scan_csv_files()
                dpg.add_text("Load Data:")
                dpg.add_combo(items=csv_files, default_value="Select CSV...", width=250, 
                              callback=self.load_csv_from_combo, tag="combo_csv")

            dpg.add_separator()

            # --- MIDDLE (Rows) ---
            with dpg.child_window(tag="rows_container", border=False, height=-60):
                self.add_row()

            # --- BOTTOM BAR ---

            # --- RENDER BUTTON ---
            with dpg.group(horizontal=True):
                dpg.add_combo(items=["None", "Density (Raw)", "Density (Filtered)"], 
                              default_value="None", tag="combo_viz_mode", width=200)
                dpg.add_checkbox(label="Show Legend", default_value=True, tag="chk_legend")
                dpg.add_button(label="RENDER SCENE", width=150, callback=self.run_render, tag="btn_render")
        
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("Primary Window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()

