"""
Pure business logic for region loading/validation, CSV parsing and color mapping.
"""
import json
import pandas as pd
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from src.logger_config import log

# --- Models ---
@dataclass(frozen=True)
class RegionItem:
    acronym: str
    name: str
    
    @property
    def display(self) -> str:
        # Pipe separator as agreed for GUI parsing
        return f"{self.acronym} | {self.name}"

# --- Loading Config ---
def load_regions_config(json_path: str) -> List[RegionItem]:
    path = Path(json_path)
    if not path.exists():
        return []
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"JSON Error: {e}")
        return []

    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str):
                items.append(RegionItem(acronym=str(k), name=str(v)))
    
    items.sort(key=lambda x: x.acronym)
    return items

# --- Color & CSV Logic (NEW) ---

def get_preset_hex(index: int) -> str:
    PRESET_COLORS = [
        "#4682B4", "#DC143C", "#FFA500", "#228B22", 
        "#8A2BE2", "#008080", "#FFD700", "#708090"
    ]
    return PRESET_COLORS[index % len(PRESET_COLORS)]

def hex_to_rgb(hex_str: str) -> List[int]:
    h = hex_str.lstrip('#')
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]

def process_csv_data(file_path: str, colormap_name="viridis") -> Tuple[List[dict], float, float]:
    try:
        df = pd.read_csv(file_path)
        # Check columns (support the new optional is_seed column)
        if 'acronym' not in df.columns or 'value' not in df.columns:
            raise ValueError("CSV must have 'acronym' and 'value' columns")
            
        # If is_seed does not exist (old CSVs), create it as False
        if 'is_seed' not in df.columns:
            df['is_seed'] = False
            
    except Exception as e:
        log.error(f"CSV Load Error: {e}")
        return []

    # 1. Normalize Values
    # We need to normalize based on the MAX value across all relevant target columns to keep scales consistent?
    # Or normalize per-mode? Usually consistent scale is better for comparison.
    # Let's find the global max of targets across all value columns to have a fixed scale.
    
    value_cols = ['value_mean', 'value_ipsi', 'value_contra', 'value_left', 'value_right']
    # Filter columns that actually exist in the CSV (backward compatibility)
    present_cols = [c for c in value_cols if c in df.columns]
    
    # default fallback
    if not present_cols and 'value' in df.columns:
        present_cols = ['value']
        # Map 'value' to 'value_mean' for consistency
        df['value_mean'] = df['value'] 
    
    # Get max for normalization (ignoring Seed)
    targets_df = df[df['is_seed'] == False]
    
    if not targets_df.empty and present_cols:
        # Get global max across all value columns for targets
        v_max = targets_df[present_cols].max().max()
        v_min = 0.0 
        norm = mcolors.Normalize(vmin=v_min, vmax=v_max)
    else:
        v_min, v_max = 0.0, 1.0
        norm = mcolors.Normalize(vmin=0, vmax=1)
    
    cmap = cm.get_cmap(colormap_name)
    
    results = []
    for _, row in df.iterrows():
        item = {
            "acronym": str(row['acronym']),
            "is_seed": bool(row['is_seed'])
        }
        
        if row['is_seed']:
            seed_color = "#000000"
            for col in value_cols: # Ensure all possible keys exist for seed
                 suffix = col.replace('value_', '')
                 item[f"color_{suffix}"] = seed_color
                 item[col] = row.get(col, 1.0)
        else:
            # Calculate color for each available metric
            for col in present_cols:
                val = row[col]
                # Handle NaN
                if pd.isna(val): val = 0.0
                
                rgba = cmap(norm(val))
                suffix = col.replace('value_', '') # mean, ipsi, etc.
                item[f"color_{suffix}"] = mcolors.to_hex(rgba)
                item[col] = val
                
            # Fallback if color_mean missing (e.g. old CSV)
            if "color_mean" not in item and "value" in row:
                 val = row["value"]
                 item["color_mean"] = mcolors.to_hex(cmap(norm(val)))

        results.append(item)
        
    # Put the SEED at the top
    results.sort(key=lambda x: x['is_seed'], reverse=True)
        
    return results, v_min, v_max

def get_descendants(parent_acronym: str, atlas_name="allen_mouse_25um") -> List[str]:
    """
    Returns a list of all descendant acronyms for a given parent structure.
    """
    try:
        from brainglobe_atlasapi import BrainGlobeAtlas
        atlas = BrainGlobeAtlas(atlas_name)
        
        # Get ID of the parent
        parent_id = atlas.structures[parent_acronym]["id"]
        
        # Get descendants (returns list of IDs)
        descendant_ids = atlas.get_structure_descendants(parent_id)
        
        # Convert IDs back to acronyms
        descendant_acronyms = [atlas.structures[did]["acronym"] for did in descendant_ids]
        
        # Include the parent itself? Usually yes for "select all"
        descendant_acronyms.append(parent_acronym)
        
        return descendant_acronyms
    except Exception as e:
        log.error(f"[LOGIC] Failed to get descendants for {parent_acronym}: {e}")
        return []