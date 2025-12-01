import pandas as pd
import yaml
from pathlib import Path
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache
import sys

# Fix import path
sys.path.append(str(Path(__file__).resolve().parent))

# Import from existing miner
from fetch import get_experiments, DATA_RAW_PATH, CONFIG_PATH

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def run_analysis_mining():
    # 1. Setup
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    print(f"--- STARTING FULL ANALYSIS MINING FOR SEED: {seed} ---")

    # 2. Fetch Experiments
    experiments, mcc = get_experiments(seed, DATA_RAW_PATH)
    experiment_ids = experiments['id'].tolist()
    
    if not experiment_ids:
        print("[ERROR] No experiments found.")
        return

    print(f"[ANALYSIS] Found {len(experiment_ids)} experiments. Fetching unionize data...")

    # 3. Fetch Unionizes (All experiments)
    try:
        unionizes = mcc.get_structure_unionizes(experiment_ids)
    except AttributeError:
        unionizes = mcc.get_structure_unionize(experiment_ids)

    print(f"[ANALYSIS] Raw unionize rows: {len(unionizes)}")

    # 4. Enrich with Ontology (Acronyms)
    st = mcc.get_structure_tree()
    id_to_acronym = {node['id']: node['acronym'] for node in st.nodes()}
    id_to_name = {node['id']: node['name'] for node in st.nodes()}
    
    unionizes['acronym'] = unionizes['structure_id'].map(id_to_acronym)
    unionizes['region_name'] = unionizes['structure_id'].map(id_to_name)
    
    # Filter out rows where structure_id is not in our map
    unionizes = unionizes.dropna(subset=['acronym'])

    # 5. Hemisphere Logic
    # experiments df has 'id' which matches 'experiment_id' in unionizes
    # Ensure 'id' is a column
    if 'id' not in experiments.columns:
        experiments = experiments.reset_index()

    exp_meta = experiments[['id', 'gender', 'strain', 'injection_volume', 'structure_id']].copy()
    exp_meta = exp_meta.rename(columns={'id': 'experiment_id_match'})
    
    # Reset index to avoid 'id' ambiguity if it's in the index
    unionizes = unionizes.reset_index(drop=True)
    
    unionizes = unionizes.merge(exp_meta, left_on='experiment_id', right_on='experiment_id_match', how='left')
    
    # Define Hemisphere Map
    hemi_map = {1: 'Left', 2: 'Right', 3: 'Midline'}
    unionizes['target_hemisphere'] = unionizes['hemisphere_id'].map(hemi_map)

    # Determine Ipsilateral vs Contralateral
    # Assumption: Allen Connectivity Atlas injections are primarily RIGHT hemisphere.
    # But let's be safe. If we assume Injection is Right (2):
    # Target Right (2) -> Ipsilateral
    # Target Left (1) -> Contralateral
    # Target Midline (3) -> Midline
    
    # TODO: If we want to be 100% precise we would check injection coordinates, 
    # but for now we assume the standard Right-side injection protocol or treat 'hemisphere_id' 2 as Ipsi.
    
    def get_lateralization(row):
        # Assuming Injection is always Right (2) for this dataset as per standard Allen protocol
        # If we find left injections, this logic needs update.
        if row['hemisphere_id'] == 2:
            return 'Ipsilateral'
        elif row['hemisphere_id'] == 1:
            return 'Contralateral'
        else:
            return 'Midline'

    unionizes['lateralization'] = unionizes.apply(get_lateralization, axis=1)

    # 6. Select Columns
    cols_to_keep = [
        'experiment_id', 'acronym', 'region_name', 
        'hemisphere_id', 'target_hemisphere', 'lateralization',
        'projection_density', 'projection_energy', 'projection_volume',
        'volume', 'is_injection',
        'gender', 'strain', 'injection_volume'
    ]
    
    final_df = unionizes[cols_to_keep].copy()

    # 7. Save
    output_dir = Path(__file__).resolve().parent.parent.parent / "analysis" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{seed}_full_analysis.csv"
    
    final_df.to_csv(output_file, index=False)
    print(f"\n[SUCCESS] Full analysis data saved to: {output_file}")
    print(final_df.head())

if __name__ == "__main__":
    run_analysis_mining()
