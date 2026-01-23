import customtkinter as ctk
import yaml
import sys
import os
import subprocess
from pathlib import Path

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class NeuroglobeLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Setup Paths ---
        self.base_path = Path(__file__).resolve().parent
        self.root_path = self.base_path.parent
        self.config_path = self.base_path / "launcher_text.yaml"

        # --- Load Config ---
        self.text_config = self.load_text_config()

        # --- Window Setup ---
        self.title("Neuroglobe Launcher")
        self.geometry("600x500")
        self.resizable(False, False)

        # --- UI Layout ---
        self.create_widgets()

    def load_text_config(self):
        default_config = {
            "welcome_title": "Neuroglobe",
            "welcome_description": "Welcome to Neuroglobe.",
            "miner_button": "Open Miner",
            "viewer_button": "Open Viewer",
            "footer_text": "v4.0"
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    return {**default_config, **yaml.safe_load(f)}
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config

    def create_widgets(self):
        # Grid Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # Header
        self.grid_rowconfigure(1, weight=2)  # Content
        self.grid_rowconfigure(2, weight=1)  # Footer

        # --- Main Frame ---
        main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main_frame.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        # 1. Header (Title)
        self.label_title = ctk.CTkLabel(
            main_frame, 
            text=self.text_config["welcome_title"], 
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.label_title.grid(row=0, column=0, pady=(20, 10))

        # 2. Description
        self.label_desc = ctk.CTkLabel(
            main_frame, 
            text=self.text_config["welcome_description"], 
            font=ctk.CTkFont(size=14),
            wraplength=500,
            justify="center"
        )
        self.label_desc.grid(row=1, column=0, pady=(0, 30))

        # 3. Buttons Frame
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=10)

        # Miner Button
        self.btn_miner = ctk.CTkButton(
            btn_frame,
            text=self.text_config["miner_button"],
            command=self.launch_miner,
            height=50,
            width=200,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#2CC985", hover_color="#229965" # Greenish hint for Mining/Data
        )
        self.btn_miner.grid(row=0, column=0, padx=20)

        # Viewer Button
        self.btn_viewer = ctk.CTkButton(
            btn_frame,
            text=self.text_config["viewer_button"],
            command=self.launch_viewer,
            height=50,
            width=200,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#3B8ED0", hover_color="#36719F" # Allen Blue reference
        )
        self.btn_viewer.grid(row=0, column=1, padx=20)

        # 4. Footer
        self.label_footer = ctk.CTkLabel(
            main_frame, 
            text=self.text_config["footer_text"], 
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.label_footer.grid(row=3, column=0, pady=(40, 0))

    def get_env_python(self, env_name):
        """
        Attempts to find the python executable for a given conda environment.
        Assumes standard Miniforge/Anaconda structure on Windows.
        """
        # 1. Try to find where the current python is, and guess the envs folder
        curr_python = Path(sys.executable)
        # e.g., C:\Users\David\miniforge3\envs\current_env\python.exe
        # or C:\Users\David\miniforge3\python.exe
        
        # Heuristic: Look for 'envs' directory
        # Walk up until we find 'miniforge3' or 'anaconda3' or just 'envs'
        candidates = []
        
        # Known user path based on reports
        user_envs_path = Path(r"C:\Users\David\miniforge3\envs")
        if user_envs_path.exists():
             candidates.append(user_envs_path / env_name / "python.exe")

        # Fallback: relative to current env
        # If we are in ...\envs\A, then ...\envs\B is parallel
        if "envs" in str(curr_python):
            # Go up to 'envs' folder
            # e.g. ...\envs\A\python.exe -> parent=A, parent.parent=envs
            envs_dir = curr_python.parent.parent
            candidates.append(envs_dir / env_name / "python.exe")

        for path in candidates:
            if path.exists():
                print(f"[LAUNCHER] Found {env_name} environment: {path}")
                return str(path)
        
        # If not found, warn and fallback to system python (which will likely fail if deps missing)
        print(f"[WARNING] Could not find environment '{env_name}'. Using current python.")
        return sys.executable

    def launch_miner(self):
        print("Launching Miner GUI...")
        miner_script = self.base_path / "miner_gui.py"
        python_exe = self.get_env_python("allensdk")
        
        if not miner_script.exists():
            print("[DEV] Miner GUI script missing.")
            return

        subprocess.Popen([python_exe, str(miner_script)])

    def launch_viewer(self):
        print("Launching Viewer...")
        # Try finding main.py in src/viewer/main.py (standard) or root
        viewer_script = self.root_path / "src" / "viewer" / "main.py"
        
        if not viewer_script.exists():
             # Fallback
             viewer_script = self.root_path / "main.py"

        if viewer_script.exists():
            python_exe = self.get_env_python("brainglobe_render")
            print(f"[LAUNCHER] Starting Viewer with: {python_exe}")
            subprocess.Popen([python_exe, str(viewer_script)])
        else:
            print(f"[ERROR] Viewer script not found at {viewer_script}")

if __name__ == "__main__":
    app = NeuroglobeLauncher()
    app.mainloop()
