import sys
import yaml
import json
from pathlib import Path
from datetime import datetime
import pandas as pd



from neuroglobe.projections.viewer import logic
from neuroglobe.projections.viewer import rendering
from neuroglobe.projections.viewer import filter_tracts
from neuroglobe.projections.definitions import PROJECT_ROOT, CONFIGS_DIR, SCENES_DIR, TRACTS_DIR
from neuroglobe.projections.logger_config import log
from neuroglobe.core.provenance import (
    artifact_manifest,
    canonical_json_hash,
    file_sha256,
    write_json_atomic,
)

CONFIG_PATH = CONFIGS_DIR / "regions.json"
TRACT_VISUALIZATION_MODES = ("None", "Raw Volume", "Filtered Mesh")
TRACT_VOLUME_METRICS = ("density", "energy")


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
        self.current_filtered_path: Optional[Path] = None
        self.current_csv_path: Optional[Path] = None
        self.current_csv_manifest: Dict[str, Any] = {}
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
            csv_path = Path(file_path)
            df = pd.read_csv(csv_path)
            self.current_csv_path = csv_path
            manifest_path = csv_path.with_suffix(".manifest.json")
            if manifest_path.exists():
                self.current_csv_manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
            else:
                self.current_csv_manifest = {}
                log.warning("CSV provenance manifest not found: %s", manifest_path)
            if 'tract_experiment_id' in df.columns:
                self.current_tract_id = int(df['tract_experiment_id'].iloc[0])
                self.current_filtered_path = None
                log.info(f"[CONTROLLER] Found linked tractography ID: {self.current_tract_id}")
                return self.current_tract_id
            else:
                self.current_tract_id = None
                self.current_filtered_path = None
                return None
        except Exception as e:
            log.error(f"Metadata read error: {e}")
            self.current_tract_id = None
            self.current_filtered_path = None
            self.current_csv_path = None
            self.current_csv_manifest = {}
            return None

    def process_csv_data(self, file_path: str) -> List[dict]:
        """
        Wrapper for logic.process_csv_data that also updates internal scalar state.
        
        Args:
            file_path: Path to the CSV file.
            
        Returns:
            Dictionary mapping acronyms to scalar values.
        """
        try:
            result = logic.process_csv_data(file_path, colormap_name="viridis")
        except logic.CSVDataError as error:
            log.error("CSV Load Error: %s", error)
            self.current_scalar_min = 0.0
            self.current_scalar_max = 1.0
            return []
        self.current_scalar_min = result.value_min
        self.current_scalar_max = result.value_max
        return result.items

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

    def filter_tracts(
        self,
        metric: str = "density",
        status_callback: Optional[Callable[[str], None]] = None,
        target_regions: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
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

        raw_path = self._find_raw_tract(metric)

        if raw_path is None:
            return False, f"Error: Raw {metric} file not found."

        if status_callback: status_callback(f"Status: Filtering {metric.capitalize()}... (Please Wait)")
        log.info(f"[CONTROLLER] Starting Filter Process for {metric}...")
        
        if target_regions is None:
            target_regions = filter_tracts.load_targets_from_config()
        target_regions = list(dict.fromkeys(target_regions))
        source_sha256 = file_sha256(raw_path)
        filter_key = {
            "experiment_id": self.current_tract_id,
            "metric": metric,
            "targets": target_regions,
            "source_sha256": source_sha256,
        }
        config_hash = canonical_json_hash(filter_key)
        output_filename = (
            f"{self.current_tract_id}_{metric}_{config_hash}.vtk"
        )
        output_path = self.tracts_dir / output_filename

        try:
            output = filter_tracts.run_filter(
                input_path=raw_path,
                output_path=output_path,
                target_regions=target_regions,
            )
            if output and output.exists():
                sidecar = artifact_manifest(
                    artifact_type="filtered_projection_mesh",
                    experiment_id=self.current_tract_id,
                    metric=metric,
                    targets=target_regions,
                    config_hash=config_hash,
                    source={
                        "path": raw_path.name,
                        "sha256": source_sha256,
                    },
                    output={
                        "path": output.name,
                        "sha256": file_sha256(output),
                    },
                )
                write_json_atomic(output.with_suffix(".manifest.json"), sidecar)
                self.current_filtered_path = output
                return True, f"Status: Filtered {metric} ready!"
            else:
                return False, "Error: Filtering failed (check console)."
        except Exception as e:
             log.error(f"[CONTROLLER] Exception: {e}")
             return False, f"Error during filtering: {e}"

    def _find_raw_tract(self, metric: str) -> Optional[Path]:
        candidates = [
            self.tracts_dir / f"{self.current_tract_id}_{metric}.nrrd",
            self.tracts_dir / f"{self.current_tract_id}_{metric}.mhd",
        ]
        if metric == "density":
            candidates.append(self.tracts_dir / f"{self.current_tract_id}.nrrd")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def render_scene(self, 
                     selection: List[Dict[str, Any]], 
                     viz_mode: str, 
                     seed_name: str, 
                     is_csv_seed: bool, 
                     show_legend: bool = True, 
                     data_mode: str = "Mean",
                     metric: str = "density",
                     status_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Orchestrates the rendering of the 3D Scene.
        """
        if viz_mode not in TRACT_VISUALIZATION_MODES:
            return False, f"Error: Unsupported visualization mode: {viz_mode}"
        if metric not in TRACT_VOLUME_METRICS:
            return False, f"Error: Unsupported tract metric: {metric}"
        if not selection:
            return False, "Error: No valid regions selected."

        engine = self.get_lazy_engine(status_callback)

        # --- TRACTOGRAPHY MANAGEMENT ---
        tract_path = None
        
        if viz_mode == "None":
            tract_path = None
            log.info("[CONTROLLER] Viz Mode: None (Tracts hidden)")

        elif viz_mode in {"Raw Volume", "Density (Raw)"}:
            fixed_path = self.tracts_dir / f"{self.current_tract_id}_{metric}_fixed.vtk"
            raw_path = self._find_raw_tract(metric)

            if fixed_path.exists():
                tract_path = fixed_path
                log.info(f"[CONTROLLER] Using FIXED {metric} (Mesh): {fixed_path.name}")
            elif raw_path is not None:
                tract_path = raw_path
                log.info(f"[CONTROLLER] Using RAW {metric}: {raw_path.name}")
            else:
                log.warning("[CONTROLLER] Raw %s file not found", metric)
                if status_callback:
                    status_callback(f"Error: Raw {metric} file not found.")
                return False, f"Error: Raw {metric} file not found."

        elif viz_mode in {"Filtered Mesh", "Density (Filtered)"}:
            filtered_path = self.current_filtered_path
            if filtered_path and filtered_path.exists():
                sidecar_path = filtered_path.with_suffix(".manifest.json")
                try:
                    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    if int(sidecar["experiment_id"]) != int(self.current_tract_id):
                        raise ValueError("experiment ID mismatch")
                    if sidecar.get("metric") != metric:
                        raise ValueError("metric mismatch")
                except Exception as error:
                    return False, f"Error: Filter provenance is invalid: {error}"
                tract_path = filtered_path
                log.info(f"[CONTROLLER] Using FILTERED {metric}: {filtered_path.name}")
            else:
                log.warning(f"[CONTROLLER] Filtered file not found. Run 'Filter Tracts' first.")
                return False, "Error: No filtered data. Click 'Filter Tracts' first."

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
            "tracts_enabled": tract_path is not None,
            "tract_file_used": tract_path.name if tract_path else "None",
            "metric_used": metric,
            "viz_mode": viz_mode,
            "data_mode": data_mode, # Track which mode was used
            "targets_rendered": [s['acronym'] for s in selection if s['acronym'] != seed_name],
            "alpha_used": alpha,
            "scalar_min": self.current_scalar_min,
            "scalar_max": self.current_scalar_max
            ,
            "coordinate_convention": "Allen CCF: x=AP, y=DV, z=ML; units=um",
            "connectivity_csv": self.current_csv_path.name
            if self.current_csv_path
            else None,
            "connectivity_csv_sha256": file_sha256(self.current_csv_path)
            if self.current_csv_path and self.current_csv_path.exists()
            else None,
            "connectivity_manifest": self.current_csv_manifest,
        }

        if status_callback: status_callback("Rendering... Press 'S' to save scene.")
        
        # Rendering call
        try:
            result = engine.render_scene(
                selection,
                tract_file=tract_path,
                alpha=alpha,
                output_dir=self.scenes_dir,
                metadata=metadata,
                visualization_mode=viz_mode,
                show_legend=show_legend,
                data_mode=data_mode,
            )
        except Exception as error:
            log.exception("Render failed")
            return False, f"Error: Render failed: {error}"
        if not result.success:
            details = "; ".join(result.errors[:3]) or "no region was rendered"
            return False, f"Error: Render incomplete: {details}"
        return True, "Status: Render Complete (Press 'S' to save)"
