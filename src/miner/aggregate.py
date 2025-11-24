import pandas as pd
import yaml
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# Importa variabili dal fetcher
from fetch import get_experiments, DATA_RAW_PATH, CONFIG_PATH

# --- NUOVO: Importiamo la funzione per i tratti ---
from extract_tracts import fetch_and_process_tracts

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def download_and_aggregate(experiments_df, mcc, config):
    """
    Scarica dati numerici (CSV) e il volume 3D (Tracts) per il miglior esperimento.
    """
    experiment_ids = experiments_df['id'].tolist()
    metric = config["processing"]["metric"] 
    agg_mode = config["processing"]["aggregation_mode"]
    
    # --- 1. Selezione "Best Experiment" per la Trattografia ---
    # Ordiniamo per volume di iniezione decrescente e prendiamo il primo.
    if not experiments_df.empty:
        best_exp = experiments_df.sort_values(by="injection_volume", ascending=False).iloc[0]
        best_id = int(best_exp['id'])
        print(f"\n[MINER] Selected Representative Experiment: {best_id}")
        print(f"        (Injection Vol: {best_exp['injection_volume']:.3f} mm3)")
        
        # Scarichiamo il volume 3D
        success = fetch_and_process_tracts(best_id)
        if success:
            print(f"[MINER] Tractography volume secured for {best_id}")
        else:
            print(f"[WARNING] Could not download tracts for {best_id}")
    else:
        print("[WARNING] No experiments available for tractography.")

    # --- 2. Download Dati Numerici (Unionize) ---
    print(f"\n[MINER] Downloading unionize data for {len(experiment_ids)} experiments...")
    
    try:
        unionizes = mcc.get_structure_unionizes(experiment_ids)
    except AttributeError:
        unionizes = mcc.get_structure_unionize(experiment_ids)
    
    print(f"[MINER] Raw rows downloaded: {len(unionizes)}")

    # 3. Get Ontology (Manual Build)
    st = mcc.get_structure_tree()
    print("[MINER] Building ontology map manually...")
    id_to_acronym_map = {node['id']: node['acronym'] for node in st.nodes()}
    
    # 4. Filter Data & Mark Seed
    valid_df = unionizes[unionizes['structure_id'].isin(id_to_acronym_map.keys())].copy()
    valid_df['acronym'] = valid_df['structure_id'].map(id_to_acronym_map)
    
    seed_df = valid_df[valid_df['is_injection'] == True].copy()
    target_df = valid_df[valid_df['is_injection'] == False].copy()
    
    # 5. Aggregation (Targets)
    print(f"[MINER] Aggregating targets using mode: '{agg_mode}'...")
    if agg_mode == 'mean':
        agg_targets = target_df.groupby('acronym')[metric].mean()
    elif agg_mode == 'median':
        agg_targets = target_df.groupby('acronym')[metric].median()
    elif agg_mode == 'max':
        agg_targets = target_df.groupby('acronym')[metric].max()
        
    final_targets = agg_targets.reset_index()
    final_targets.columns = ['acronym', 'value']
    final_targets['is_seed'] = False 
    
    # 6. Handle Seed
    seed_acronyms = seed_df['acronym'].unique()
    seed_rows = []
    for sa in seed_acronyms:
        val = seed_df[seed_df['acronym'] == sa][metric].max()
        seed_rows.append({'acronym': sa, 'value': val, 'is_seed': True})
        
    final_seed = pd.DataFrame(seed_rows)
    
    # 7. Merge & Save
    final_df = pd.concat([final_seed, final_targets], ignore_index=True)
    final_df = final_df[(final_df['value'] > 0) | (final_df['is_seed'] == True)]
    
    # --- NUOVO: Salviamo l'ID del "Best Experiment" nel CSV ---
    # Aggiungiamo una colonna 'best_experiment_id' (lo ripetiamo su tutte le righe, è un metadato)
    if not experiments_df.empty:
        final_df['tract_experiment_id'] = best_id
    
    return final_df

if __name__ == "__main__":
    # 1. Setup
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    # 2. Fetch Experiments
    experiments, mcc = get_experiments(seed, DATA_RAW_PATH)
    
    # 3. Process (Ora include il download tracts)
    final_data = download_and_aggregate(experiments, mcc, config)
    
    # 4. Save
    output_filename = f"{seed}_connectivity.csv"
    output_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_data.to_csv(output_path, index=False)
    
    print(f"\n[SUCCESS] Data saved to: {output_path}")
    if 'tract_experiment_id' in final_data.columns:
        print(f"          Linked Tractography ID: {final_data['tract_experiment_id'].iloc[0]}")