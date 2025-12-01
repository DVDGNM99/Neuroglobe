"""
Pure business logic for region loading/validation, CSV parsing and color mapping.
"""
import json
import pandas as pd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

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
        print(f"JSON Error: {e}")
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
        # Check columns (supportiamo anche la nuova colonna is_seed opzionale)
        if 'acronym' not in df.columns or 'value' not in df.columns:
            raise ValueError("CSV must have 'acronym' and 'value' columns")
            
        # Se is_seed non esiste (vecchi CSV), crealo come False
        if 'is_seed' not in df.columns:
            df['is_seed'] = False
            
    except Exception as e:
        print(f"CSV Load Error: {e}")
        return []

    # 1. Normalize Values (Escludendo il seed per non sballare la scala!)
    # Normalizziamo solo i target, altrimenti il seed (che ha valore altissimo) schiaccia tutti gli altri a zero.
    target_values = df[df['is_seed'] == False]['value'].values
    
    if len(target_values) > 0:
        v_min, v_max = target_values.min(), target_values.max()
        norm = mcolors.Normalize(vmin=v_min, vmax=v_max)
    else:
        v_min, v_max = 0.0, 1.0
        norm = mcolors.Normalize(vmin=0, vmax=1)
    
    cmap = plt.get_cmap(colormap_name)
    
    results = []
    for _, row in df.iterrows():
        
        if row['is_seed']:
            # --- SPECIAL COLOR FOR SEED ---
            hex_color = "#000000" # Nero puro
            # O un grigio scuro se preferisci: "#333333"
        else:
            rgba = cmap(norm(row['value'])) 
            hex_color = mcolors.to_hex(rgba)
        
        results.append({
            "acronym": str(row['acronym']),
            "color": hex_color,
            "is_seed": bool(row['is_seed'])
        })
        
    # Mettiamo il SEED in cima alla lista così appare per primo nella GUI
    results.sort(key=lambda x: x['is_seed'], reverse=True)
        
    # Mettiamo il SEED in cima alla lista così appare per primo nella GUI
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
        print(f"[LOGIC] Failed to get descendants for {parent_acronym}: {e}")
        return []