import pandas as pd
import yaml
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# Importa variabili dal fetcher
from fetch import get_experiments, DATA_RAW_PATH, CONFIG_PATH

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def download_and_aggregate(experiments_df, mcc, config):
    """
    Scarica dati, include il SEED (Iniezione) e crea flag 'is_seed'.
    """
    experiment_ids = experiments_df['id'].tolist()
    metric = config["processing"]["metric"] 
    agg_mode = config["processing"]["aggregation_mode"]
    
    print(f"\n[MINER] Downloading unionize data for {len(experiment_ids)} experiments...")
    
    try:
        unionizes = mcc.get_structure_unionizes(experiment_ids)
    except AttributeError:
        unionizes = mcc.get_structure_unionize(experiment_ids)
    
    print(f"[MINER] Raw rows downloaded: {len(unionizes)}")

    # 2. Get Ontology (Manual Build)
    st = mcc.get_structure_tree()
    print("[MINER] Building ontology map manually...")
    id_to_acronym_map = {node['id']: node['acronym'] for node in st.nodes()}
    
    # 3. Filter Data & Mark Seed
    # Filtriamo solo ID validi
    valid_df = unionizes[unionizes['structure_id'].isin(id_to_acronym_map.keys())].copy()
    
    # Aggiungiamo l'acronimo
    valid_df['acronym'] = valid_df['structure_id'].map(id_to_acronym_map)
    
    # Separiamo Injection (Seed) da Projections (Targets)
    # Il seed è dove is_injection è True
    seed_df = valid_df[valid_df['is_injection'] == True].copy()
    target_df = valid_df[valid_df['is_injection'] == False].copy()
    
    # 4. Aggregation (Targets)
    print(f"[MINER] Aggregating targets using mode: '{agg_mode}'...")
    if agg_mode == 'mean':
        agg_targets = target_df.groupby('acronym')[metric].mean()
    elif agg_mode == 'median':
        agg_targets = target_df.groupby('acronym')[metric].median()
    elif agg_mode == 'max':
        agg_targets = target_df.groupby('acronym')[metric].max()
        
    # Crea DataFrame finale per i target
    final_targets = agg_targets.reset_index()
    final_targets.columns = ['acronym', 'value']
    final_targets['is_seed'] = False # Questi sono target
    
    # 5. Handle Seed (Injection Site)
    # Per il seed, prendiamo sempre il valore MAX o MEAN per rappresentarlo
    # (Spesso ci sono più righe per il seed se ci sono più esperimenti)
    seed_acronyms = seed_df['acronym'].unique()
    seed_rows = []
    for sa in seed_acronyms:
        # Valore fittizio alto o reale, l'importante è il flag is_seed
        val = seed_df[seed_df['acronym'] == sa][metric].max()
        seed_rows.append({'acronym': sa, 'value': val, 'is_seed': True})
        
    final_seed = pd.DataFrame(seed_rows)
    
    # 6. Merge
    final_df = pd.concat([final_seed, final_targets], ignore_index=True)
    
    # Rimuovi valori a zero (ma tieni il seed anche se fosse zero, per sicurezza)
    final_df = final_df[(final_df['value'] > 0) | (final_df['is_seed'] == True)]
    
    return final_df

if __name__ == "__main__":
    # 1. Setup
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    # 2. Fetch Experiments
    experiments, mcc = get_experiments(seed, DATA_RAW_PATH)
    
    # 3. Process
    final_data = download_and_aggregate(experiments, mcc, config)
    
    # 4. Save
    output_filename = f"{seed}_connectivity.csv"
    output_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_data.to_csv(output_path, index=False)
    
    print(f"\n[SUCCESS] Data saved to: {output_path}")
    print(f"          Includes Seed Flag: {final_data['is_seed'].sum()} seed regions found.")
    print(final_data.head())