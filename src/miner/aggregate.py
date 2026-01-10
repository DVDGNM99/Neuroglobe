import sys
from pathlib import Path
import pandas as pd
import yaml
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

# Ensure src is in path
# Ensure src is in path (prioritize local project over installed packages)
root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

print(f"DEBUG: Running from Root: {root_path}")

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

    # --- 3. Get Ontology (Manual Build) ---
    st = mcc.get_structure_tree()
    log.info("[MINER] Building ontology map manually...")
    id_to_acronym = {node['id']: node['acronym'] for node in st.nodes()}
    
    # Delegate pure logic to helper function
    final_df = process_aggregation(unionizes, experiments_df, id_to_acronym, metric, agg_mode, best_id)
    
    return final_df

def process_aggregation(unionizes, experiments_df, id_to_acronym, metric, agg_mode, best_id=None):
    """
    Pure logic function for aggregating unionize data.
    Separated for easier unit testing.
    """
    # --- 4. Prepare Data ---
    # Convert structure_id to acronym
    processing_df = unionizes.copy()
    processing_df['acronym'] = processing_df['structure_id'].map(id_to_acronym)
    
    # Filter out entries not in our map (usually root or artifacts)
    valid_df = processing_df.dropna(subset=['acronym']).copy()
    
    # Enrich with Injection Hemisphere info
    # We map experiment_id to its injection_x to determine side
    if not experiments_df.empty and 'injection_x' in experiments_df.columns:
        exp_id_to_x = dict(zip(experiments_df['id'], experiments_df['injection_x']))
    else:
        exp_id_to_x = {}
        
    # Logic: Midline ~ 5700 um (CCFv3). 
    # X < 5700: Left
    # X > 5700: Right
    # Hemisphere IDs in Unionize: 1=Left, 2=Right, 3=Both
    
    def get_injection_hemisphere_id(exp_id):
        x = exp_id_to_x.get(exp_id, 5700) # Default to Midline/Both if unknown
        return 1 if x < 5700 else 2
        
    valid_df['inj_hemi'] = valid_df['experiment_id'].apply(get_injection_hemisphere_id)
    
    # Calculate Ipsi/Contra
    # If projection_hemisphere (hemisphere_id) == inj_hemi -> Ipsi
    valid_df['is_ipsi'] = valid_df['hemisphere_id'] == valid_df['inj_hemi']
    # Contra is opposite side AND not midline (3)
    valid_df['is_contra'] = (valid_df['hemisphere_id'] != valid_df['inj_hemi']) & (valid_df['hemisphere_id'] != 3)

    # Separate Seed and Targets
    seed_df = valid_df[valid_df['is_injection'] == True].copy()
    target_df = valid_df[valid_df['is_injection'] == False].copy()
    
    # --- 5. Aggregation (Targets) ---
    log.info(f"[MINER] Aggregating targets using mode: '{agg_mode}'...")
    
    # Aggregation helper
    def agg_func(df, col):
        if df.empty: return pd.Series(dtype=float)
        if agg_mode == 'mean': return df.groupby('acronym')[col].mean()
        elif agg_mode == 'median': return df.groupby('acronym')[col].median()
        elif agg_mode == 'max': return df.groupby('acronym')[col].max()
        return df.groupby('acronym')[col].mean()

    # 1. Overall Mean (Legacy)
    s_mean = agg_func(target_df, metric)
    
    # 2. Ipsilateral
    df_ipsi = target_df[target_df['is_ipsi'] == True]
    s_ipsi = agg_func(df_ipsi, metric)
    
    # 3. Contralateral
    df_contra = target_df[target_df['is_contra'] == True]
    s_contra = agg_func(df_contra, metric)
    
    # 4. Left Hemisphere (hemisphere_id == 1)
    df_left = target_df[target_df['hemisphere_id'] == 1]
    s_left = agg_func(df_left, metric)
    
    # 5. Right Hemisphere (hemisphere_id == 2)
    df_right = target_df[target_df['hemisphere_id'] == 2]
    s_right = agg_func(df_right, metric)
    
    # Combine into one DataFrame
    # Need to handle alignment of indices (acronyms)
    # Using pd.DataFrame(dict) auto-aligns on index (acronym)
    final_df = pd.DataFrame({
        'value_mean': s_mean,
        'value_ipsi': s_ipsi,
        'value_contra': s_contra,
        'value_left': s_left,
        'value_right': s_right
    })
    
    final_df = final_df.reset_index()
    
    # Fill NaNs with 0 (e.g. if a region has no contralateral projection)
    final_df = final_df.fillna(0)
    
    # Legacy compatibility: 'value' column = 'value_mean'
    final_df['value'] = final_df['value_mean']
    final_df['is_seed'] = False
    
    # --- 6. Handle Seed ---
    # For seed, we usually just take the max value as reference
    seed_acronyms = seed_df['acronym'].unique()
    seed_rows = []
    for sa in seed_acronyms:
        # Determine max value for seed (usually saturation)
        val = seed_df[seed_df['acronym'] == sa][metric].max()
        seed_rows.append({
            'acronym': sa, 
            'value': val, 
            'value_mean': val,
            'value_ipsi': val,   # Assumption: Seed is high everywhere
            'value_contra': 0,   # Seed usually doesn't cross? or maybe it does. Let's keep 0 to distinguish.
            'value_left': val,   # Simplified
            'value_right': val,  # Simplified
            'is_seed': True
        })
        
    final_seed = pd.DataFrame(seed_rows)
    
    # --- 7. Merge & Save ---
    # Combine and filter
    if not final_seed.empty:
        final_df = pd.concat([final_seed, final_df], ignore_index=True)
    
    # Filter out rows with 0 value (optimization)
    final_df = final_df[(final_df['value'] > 0) | (final_df['is_seed'] == True)]
    
    # --- NEW: Save "Best Experiment" ID ---
    if best_id is not None:
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
    # 4. Save Full Dataset
    output_filename = f"{seed}_connectivity.csv"
    output_path = PROCESSED_DATA_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_data.to_csv(output_path, index=False)
    log.info(f"[SUCCESS] Full Data saved to: {output_path}")

    # 5. Save Filtered Dataset (if configured)
    if config.get("selection", {}).get("use_custom_targets", False):
        custom_targets = config["selection"].get("custom_targets", [])
        primary_seed = config["experiment"].get("seed_acronym", "")
        
        if custom_targets:
            # Strict Filtering:
            # 1. Keep Targets: Must be in custom_targets AND NOT be a seed/injection site (avoids duplicates).
            # 2. Keep Primary Seed: The only allowed seed row.
            filtered_df = final_data[
                ((final_data['acronym'].isin(custom_targets)) & (final_data['is_seed'] == False)) | 
                ((final_data['is_seed'] == True) & (final_data['acronym'] == primary_seed))
            ]
            
            filtered_filename = f"{seed}_connectivity_filtered.csv"
            filtered_path = PROCESSED_DATA_DIR / filtered_filename
            filtered_df.to_csv(filtered_path, index=False)
            log.info(f"[SUCCESS] Filtered Data saved to: {filtered_path}")
            log.info(f"          (Cleaned up {len(final_data) - len(filtered_df)} spillover/unused regions)")
    
    if 'tract_experiment_id' in final_data.columns:
        log.info(f"          Linked Tractography ID: {final_data['tract_experiment_id'].iloc[0]}")