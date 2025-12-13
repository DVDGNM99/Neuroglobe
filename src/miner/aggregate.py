import sys
from pathlib import Path
import pandas as pd
import yaml
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# Ensure src is in path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.definitions import CONFIGS_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.logger_config import log

# Import variables from fetcher
from src.miner.fetch import get_experiments

# --- NEW: Import tract function ---
# Note: extract_tracts might need similar updates, but imported as module here
from src.miner.extract_tracts import fetch_and_process_tracts

CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def download_and_aggregate(experiments_df, mcc, config):
    """
    Downloads numeric data (CSV) and 3D volume (Tracts) for the best experiment.
    """
    experiment_ids = experiments_df['id'].tolist()
    metric = config["processing"]["metric"] 
    agg_mode = config["processing"]["aggregation_mode"]
    
    # --- 1. Select "Best Experiment" for Tractography ---
    # Sort by injection volume descending and take the first one.
    if not experiments_df.empty:
        best_exp = experiments_df.sort_values(by="injection_volume", ascending=False).iloc[0]
        best_id = int(best_exp['id'])
        log.info(f"[MINER] Selected Representative Experiment: {best_id}")
        log.info(f"        (Injection Vol: {best_exp['injection_volume']:.3f} mm3)")
        
        # Download 3D volume
        success = fetch_and_process_tracts(best_id)
        if success:
            log.info(f"[MINER] Tractography volume secured for {best_id}")
        else:
            log.warning(f"[WARNING] Could not download tracts for {best_id}")
    else:
        log.warning("[WARNING] No experiments available for tractography.")

    # --- 2. Download Numeric Data (Unionize) ---
    log.info(f"[MINER] Downloading unionize data for {len(experiment_ids)} experiments...")
    
    try:
        unionizes = mcc.get_structure_unionizes(experiment_ids)
    except AttributeError:
        unionizes = mcc.get_structure_unionize(experiment_ids)
    
    log.info(f"[MINER] Raw rows downloaded: {len(unionizes)}")

    # 3. Get Ontology (Manual Build)
    st = mcc.get_structure_tree()
    log.info("[MINER] Building ontology map manually...")
    id_to_acronym_map = {node['id']: node['acronym'] for node in st.nodes()}
    
    # 4. Filter Data & Mark Seed
    valid_df = unionizes[unionizes['structure_id'].isin(id_to_acronym_map.keys())].copy()
    valid_df['acronym'] = valid_df['structure_id'].map(id_to_acronym_map)
    
    seed_df = valid_df[valid_df['is_injection'] == True].copy()
    target_df = valid_df[valid_df['is_injection'] == False].copy()
    
    # 5. Aggregation (Targets)
    log.info(f"[MINER] Aggregating targets using mode: '{agg_mode}'...")
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
    
    # --- NEW: Save "Best Experiment" ID in CSV ---
    # Add column 'best_experiment_id' (repeating it on all rows, it's metadata)
    if not experiments_df.empty:
        final_df['tract_experiment_id'] = best_id
    
    return final_df

if __name__ == "__main__":
    # 1. Setup
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    
    # 2. Fetch Experiments
    experiments, mcc = get_experiments(seed, RAW_DATA_DIR)
    
    # 3. Process (Now includes tracts download)
    final_data = download_and_aggregate(experiments, mcc, config)
    
    # 4. Save
    output_filename = f"{seed}_connectivity.csv"
    output_path = PROCESSED_DATA_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_data.to_csv(output_path, index=False)
    
    log.info(f"[SUCCESS] Data saved to: {output_path}")
    if 'tract_experiment_id' in final_data.columns:
        log.info(f"          Linked Tractography ID: {final_data['tract_experiment_id'].iloc[0]}")