import pandas as pd
import re
import yaml
from pathlib import Path

# --- Config Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "mining_config.yaml"
DATA_DIR = BASE_DIR / "data" / "processed"

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("Config file missing!")
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def run_filter():
    # 1. Carica Configurazione
    config = load_config()
    target_seed = config["experiment"]["seed_acronym"]
    use_custom = config.get("selection", {}).get("use_custom_targets", False)
    custom_list = config.get("selection", {}).get("custom_targets", [])

    print(f"--- FILTERING FOR SEED: {target_seed} ---")
    
    # Costruiamo i nomi file basati sul seed corrente
    input_file = f"{target_seed}_connectivity.csv"
    output_file = f"{target_seed}_demo_filtered.csv"
    input_path = DATA_DIR / input_file
    output_path = DATA_DIR / output_file
    
    if not input_path.exists():
        print(f"[ERROR] File {input_file} not found.")
        print("Did you remember to run 'fetch.py' and 'aggregate.py' for this new seed?")
        return

    # 2. Carica Dati
    df = pd.read_csv(input_path)
    if 'is_seed' not in df.columns: df['is_seed'] = False

    # 3. SEED HANDLING (Rimuovi guscio esterno)
    blacklist = ["root", "grey", "CH", "Isocortex", "CTX", "BS", "HB"]
    
    seeds_df = df[df['is_seed'] == True].copy()
    
    # Cerchiamo il seed esatto
    exact_seed = seeds_df[seeds_df['acronym'] == target_seed]
    
    if not exact_seed.empty:
        # Se troviamo esattamente lui, usiamo solo lui (pulito)
        seeds_clean = exact_seed.copy()
    else:
        # Fallback: teniamo i seed che non sono blacklisted
        seeds_clean = seeds_df[~seeds_df['acronym'].isin(blacklist)].copy()

    # 4. TARGET SELECTION
    targets_source = df[df['is_seed'] == False].copy()
    
    if use_custom and custom_list:
        print(f"Using Custom Target List: {custom_list}")
        # Filtra solo le aree presenti nella lista custom
        selected_targets = targets_source[targets_source['acronym'].isin(custom_list)].copy()
        
        # Check se abbiamo trovato tutto
        found = selected_targets['acronym'].unique()
        missing = set(custom_list) - set(found)
        if missing:
            print(f"[WARNING] Some requested targets have 0 connectivity or invalid names: {missing}")
    else:
        # Logica Top 5 (Vecchio metodo)
        print("Using Automatic Top-5 Selection")
        def is_layer(x): return bool(re.search(r'\d', str(x)))
        targets_clean = targets_source[~targets_source['acronym'].apply(is_layer)].copy()
        targets_sorted = targets_clean.sort_values(by='value', ascending=False).reset_index(drop=True)
        indices = [0, 10, 30, 60, 100]
        valid_idxs = [i for i in indices if i < len(targets_sorted)]
        selected_targets = targets_sorted.iloc[valid_idxs].copy()

    # 5. Unisci e Salva
    final_demo = pd.concat([seeds_clean, selected_targets], ignore_index=True)
    final_demo.to_csv(output_path, index=False)
    
    print("\n--- RESULT PREVIEW ---")
    print(final_demo[['acronym', 'value', 'is_seed']])
    print(f"\n[DONE] Saved to: {output_path}")

if __name__ == "__main__":
    run_filter()