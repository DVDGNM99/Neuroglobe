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
    config = load_config()
    target_seed = config["experiment"]["seed_acronym"]
    use_custom = config.get("selection", {}).get("use_custom_targets", False)
    custom_list = config.get("selection", {}).get("custom_targets", [])

    print(f"--- FILTERING FOR SEED: {target_seed} ---")
    
    input_file = f"{target_seed}_connectivity.csv"
    output_file = f"{target_seed}_demo_filtered.csv"
    input_path = DATA_DIR / input_file
    output_path = DATA_DIR / output_file
    
    if not input_path.exists():
        print(f"[ERROR] File {input_file} not found.")
        return

    # 1. Carica Dati Grezzi
    df = pd.read_csv(input_path)
    if 'is_seed' not in df.columns: df['is_seed'] = False

    # --- SALVIAMO L'ID DEI TRATTI ---
    # Se esiste la colonna tract_experiment_id, salviamone il valore
    # per riapplicarlo alla fine, altrimenti lo perdiamo filtrando.
    tract_id = None
    if 'tract_experiment_id' in df.columns:
        tract_id = df['tract_experiment_id'].iloc[0]
        print(f"[FILTER] Preserving Tractography ID: {tract_id}")

    # 2. Pulizia Blacklist (Gusci esterni)
    blacklist = ["root", "grey", "CH", "Isocortex", "CTX", "BS", "HB"]
    seeds_df = df[df['is_seed'] == True].copy()
    
    # Gestione Seed
    exact_seed = seeds_df[seeds_df['acronym'] == target_seed]
    seeds_clean = exact_seed.copy() if not exact_seed.empty else seeds_df[~seeds_df['acronym'].isin(blacklist)].copy()

    # 3. Selezione Target
    targets_source = df[df['is_seed'] == False].copy()
    
    if use_custom and custom_list:
        print(f"Using Custom Target List: {custom_list}")
        selected_targets = targets_source[targets_source['acronym'].isin(custom_list)].copy()
    else:
        print("Using Automatic Top-5 Selection")
        def is_layer(x): return bool(re.search(r'\d', str(x)))
        targets_clean = targets_source[~targets_source['acronym'].apply(is_layer)].copy()
        targets_sorted = targets_clean.sort_values(by='value', ascending=False).reset_index(drop=True)
        # Prendiamo top 10 per sicurezza
        selected_targets = targets_sorted.iloc[:10].copy()

    # 4. Unione
    final_demo = pd.concat([seeds_clean, selected_targets], ignore_index=True)

    # --- RI-APPLICHIAMO L'ID DEI TRATTI ---
    if tract_id is not None:
        final_demo['tract_experiment_id'] = tract_id

    # 5. Salvataggio
    final_demo.to_csv(output_path, index=False)
    
    print("\n--- RESULT PREVIEW ---")
    print(final_demo[['acronym', 'value', 'is_seed']])
    print(f"\n[DONE] Saved to: {output_path}")

if __name__ == "__main__":
    run_filter()