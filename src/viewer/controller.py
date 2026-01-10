import sys
import yaml
from pathlib import Path
from datetime import datetime
import pandas as pd



from src.viewer import logic
from src.viewer import rendering
from src.viewer import filter_tracts
from src.definitions import PROJECT_ROOT, CONFIGS_DIR, SCENES_DIR, TRACTS_DIR
from src.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "regions.json"


from typing import List, Dict, Optional, Tuple, Any, Callable

class ViewerController:
    """
    Manages the application logic, bridging the GUI and the Rendering Engine.
    Handles data loading, state management, and rendering commands.
    """
    def __init__(self):
        self.mapping: List[Any] = [] 
        self.choices: List[str] = []
        self.acronym_lookup: Dict[str, str] = {} 
        self.engine: Optional[rendering.RenderEngine] = None 
        
        # Variable to track the current 3D volume ID
        self.current_tract_id: Optional[int] = None
        self.current_scalar_min: float = 0.0
        self.current_scalar_max: float = 1.0
        
        self.root_dir: Path = PROJECT_ROOT
        self.json_file: Path = CONFIG_PATH
        self.scenes_dir: Path = SCENES_DIR
        self.tracts_dir: Path = TRACTS_DIR
        
        self.load_data()

    def load_data(self) -> None:
        """Loads region configuration from JSON and initializes default choices."""
        log.info(f"Loading config from: {self.json_file}")
        self.mapping = logic.load_regions_config(str(self.json_file))
        self.choices = [x.display for x in self.mapping]
        self.acronym_lookup = {x.acronym: x.display for x in self.mapping}

    def get_lazy_engine(self, status_callback: Optional[Callable[[str], None]] = None) -> Any:
        """
        initializes the RenderEngine only when needed (Lazy Loading).
        
        Args:
            status_callback: Optional function to report loading status strings.
            
        Returns:
            The instance of rendering.RenderEngine.
        """
        if self.engine is None:
            if status_callback: status_callback("Status: Loading Atlas... (Wait)")
            self.engine = rendering.RenderEngine()
            if status_callback: status_callback("Status: Atlas Loaded.")
        return self.engine

    def load_csv_metadata(self, file_path: str) -> Optional[int]:
        """
        Reads CSV metadata to find the associated tractography Experiment ID.
        
        Args:
            file_path: Absolute path to the CSV file.
            
        Returns:
            The experiment ID (int) if found, else None.
        """
        try:
            df = pd.read_csv(file_path)
            if 'tract_experiment_id' in df.columns:
                self.current_tract_id = int(df['tract_experiment_id'].iloc[0])
                log.info(f"[CONTROLLER] Found linked tractography ID: {self.current_tract_id}")
                return self.current_tract_id
            else:
                self.current_tract_id = None
                return None
        except Exception as e:
            log.error(f"Metadata read error: {e}")
            self.current_tract_id = None
            return None

    def process_csv_data(self, file_path: str) -> Dict[str, float]:
        """
        Wrapper for logic.process_csv_data that also updates internal scalar state.
        
        Args:
            file_path: Path to the CSV file.
            
        Returns:
            Dictionary mapping acronyms to scalar values.
        """
        data, v_min, v_max = logic.process_csv_data(file_path, colormap_name="viridis")
        self.current_scalar_min = v_min
        self.current_scalar_max = v_max
        return data

    def get_descendants(self, parent_acronym: str) -> List[str]:
        """Retrieves all sub-regions for a given parent acronym."""
        return logic.get_descendants(parent_acronym)

    def scan_csv_files(self) -> List[str]:
        """
        Scans data/processed for available CSV analysis files.
        
        Returns:
            List of filenames (strings).
        """
        csv_dir = self.root_dir / "data" / "processed"
        if not csv_dir.exists(): return []
        return [f.name for f in csv_dir.glob("*.csv")]

    def filter_tracts(self, metric: str = "density", status_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Filters the raw tractography volume based on currently selected regions.
        
        Args:
            metric: The metric to filter (e.g. 'density').
            status_callback: Function to report status updates.
            
        Returns:
            Tuple (Success Boolean, Status Message).
        """
        if not self.current_tract_id:
            return False, "Error: No tractography ID loaded (Load CSV first)."

        raw_filename = f"{self.current_tract_id}_{metric}.nrrd"
        raw_path = self.tracts_dir / raw_filename
        
        # Fallback for legacy files
        if not raw_path.exists() and metric == "density":
             legacy_path = self.tracts_dir / f"{self.current_tract_id}.nrrd"
             if legacy_path.exists():
                 raw_path = legacy_path
                 log.info(f"[CONTROLLER] Using legacy density file: {raw_path.name}")

        if not raw_path.exists():
             return False, f"Error: Raw file not found: {raw_path.name}"

        if status_callback: status_callback(f"Status: Filtering {metric.capitalize()}... (Please Wait)")
        log.info(f"[CONTROLLER] Starting Filter Process for {metric}...")
        
        output_filename = f"filtered_{metric}.vtk"
        output_path = self.tracts_dir / output_filename

        try:
            output = filter_tracts.run_filter(input_path=raw_path, output_path=output_path)
            if output and output.exists():
                return True, f"Status: Filtered {metric} ready!"
            else:
                return False, "Error: Filtering failed (check console)."
        except Exception as e:
             log.error(f"[CONTROLLER] Exception: {e}")
             return False, f"Error during filtering: {e}"

    def render_scene(self, 
                     selection: List[Dict[str, Any]], 
                     viz_mode: str, 
                     seed_name: str, 
                     is_csv_seed: bool, 
                     show_legend: bool = True, 
                     data_mode: str = "Mean",
                     status_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Orchestrates the rendering of the 3D Scene.
        """
        engine = self.get_lazy_engine(status_callback)
        
        if not selection:
            return False, "Error: No valid regions selected."

        # --- TRACTOGRAPHY MANAGEMENT ---
        metric = "density" # Hardcoded for now
        tract_path = None
        
        if viz_mode == "None":
            tract_path = None
            log.info("[CONTROLLER] Viz Mode: None (Tracts hidden)")

        elif viz_mode == "Density (Raw)":
            fixed_path = self.tracts_dir / f"{self.current_tract_id}_{metric}_fixed.vtk"
            raw_path = self.tracts_dir / f"{self.current_tract_id}_{metric}.nrrd"
            legacy_path = self.tracts_dir / f"{self.current_tract_id}.nrrd"

            if fixed_path.exists():
                tract_path = fixed_path
                log.info(f"[CONTROLLER] Using FIXED {metric} (Mesh): {fixed_path.name}")
            elif raw_path.exists():
                tract_path = raw_path
                log.info(f"[CONTROLLER] Using RAW {metric}: {raw_path.name}")
            elif legacy_path.exists() and metric == "density":
                tract_path = legacy_path
                log.info(f"[CONTROLLER] Using LEGACY {metric}: {legacy_path.name}")
            else:
                log.warning(f"[CONTROLLER] Raw file not found: {raw_path.name}")
                if status_callback: status_callback("Error: Raw density file not found.")

        elif viz_mode == "Density (Filtered)":
            filtered_path = self.tracts_dir / f"filtered_{metric}.vtk"
            if filtered_path.exists():
                tract_path = filtered_path
                log.info(f"[CONTROLLER] Using FILTERED {metric}: {filtered_path.name}")
            else:
                log.warning(f"[CONTROLLER] Filtered file not found. Run 'Filter Tracts' first.")
                return False, "Error: No filtered data. Click 'Filter Tracts' first."

        elif viz_mode == "Streamlines (Tubes)":
            if self.current_tract_id:
                stream_path = self.tracts_dir / f"{self.current_tract_id}_streamlines.json"
                if stream_path.exists():
                    tract_path = stream_path
                    log.info(f"[CONTROLLER] Found Streamlines: {stream_path.name}")
                else:
                    log.warning(f"[CONTROLLER] Streamlines file not found: {stream_path.name}")
                    if status_callback: status_callback("Warning: No streamlines data found for this ID.")


        # Load external visual config for alpha
        visual_config_path = CONFIGS_DIR / "visual_config.yaml"
        try:
             with open(visual_config_path, "r") as f:
                 viz_config = yaml.safe_load(f)
                 alpha = viz_config.get("aesthetics", {}).get("default_alpha", 0.8)
        except Exception as e:
            log.warning(f"Could not load visual config: {e}. Using default alpha 0.8")
            alpha = 0.8

        metadata = {
            "experiment_seed": seed_name,
            # "timestamp": timestamp, # Timestamp will be added on save
            "source_type": "CSV Loaded" if is_csv_seed else "Manual Selection",
            "regions_count": len(selection),
            "tracts_enabled": (viz_mode != "None"),
            "tract_file_used": tract_path.name if tract_path else "None",
            "metric_used": metric,
            "viz_mode": viz_mode,
            "data_mode": data_mode, # Track which mode was used
            "targets_rendered": [s['acronym'] for s in selection if s['acronym'] != seed_name],
            "alpha_used": alpha,
            "scalar_min": self.current_scalar_min,
            "scalar_max": self.current_scalar_max
        }

        if status_callback: status_callback("Rendering... Press 'S' to save scene.")
        
        # Rendering call
        engine.render_scene(
            selection, 
            tract_file=tract_path, 
            alpha=alpha, 
            output_dir=self.scenes_dir, 
            metadata=metadata, 
            visualization_mode=viz_mode,
            show_legend=show_legend,
            data_mode=data_mode # Pass mode to Engine
        )
        
        return True, "Status: Render Complete (Press 'S' to save)"
