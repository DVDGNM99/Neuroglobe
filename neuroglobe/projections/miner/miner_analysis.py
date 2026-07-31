import pandas as pd

from neuroglobe.core.coordinates import injection_hemisphere, lateralization
from neuroglobe.projections.config import load_mining_config
from neuroglobe.projections.definitions import PROJECT_ROOT, CONFIGS_DIR, RAW_DATA_DIR
from neuroglobe.projections.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"
ANALYSIS_DATA_DIR = PROJECT_ROOT / "analysis" / "data"

def load_config():
    return load_mining_config(CONFIG_PATH)


def get_lateralization(
    hemisphere_id: int | float | None,
    injection_ml_um: float | int | None,
) -> str:
    return lateralization(
        hemisphere_id,
        injection_hemisphere(injection_ml_um),
    )

def run_analysis_mining():
    from neuroglobe.projections.miner.fetch import get_experiments

    # 1. Setup
    config = load_config()
    seed = config["experiment"]["seed_acronym"]
    log.info(f"--- STARTING FULL ANALYSIS MINING FOR SEED: {seed} ---")

    # 2. Fetch Experiments
    experiments, mcc = get_experiments(seed, RAW_DATA_DIR)
    experiment_ids = experiments['id'].tolist()
    
    if not experiment_ids:
        log.error("[ERROR] No experiments found.")
        return

    log.info(f"[ANALYSIS] Found {len(experiment_ids)} experiments. Fetching unionize data...")

    # 3. Fetch Unionizes (All experiments)
    try:
        unionizes = mcc.get_structure_unionizes(experiment_ids)
    except AttributeError:
        unionizes = mcc.get_structure_unionize(experiment_ids)

    log.info(f"[ANALYSIS] Raw unionize rows: {len(unionizes)}")

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

    required_metadata = [
        "id",
        "gender",
        "strain",
        "injection_volume",
        "structure_id",
        "injection_z",
    ]
    missing_metadata = [column for column in required_metadata if column not in experiments]
    if missing_metadata:
        raise ValueError(
            f"Experiment metadata is missing required columns: {missing_metadata}"
        )
    exp_meta = experiments[required_metadata].copy()
    exp_meta = exp_meta.rename(columns={'id': 'experiment_id_match'})
    
    # Reset index to avoid 'id' ambiguity if it's in the index
    unionizes = unionizes.reset_index(drop=True)
    
    unionizes = unionizes.merge(exp_meta, left_on='experiment_id', right_on='experiment_id_match', how='left')
    
    # Define Hemisphere Map
    hemi_map = {1: 'Left', 2: 'Right', 3: 'Midline'}
    unionizes['target_hemisphere'] = unionizes['hemisphere_id'].map(hemi_map)

    unionizes["lateralization"] = unionizes.apply(
        lambda row: get_lateralization(row["hemisphere_id"], row["injection_z"]),
        axis=1,
    )

    # 6. Select Columns
    cols_to_keep = [
        'experiment_id', 'acronym', 'region_name', 
        'hemisphere_id', 'target_hemisphere', 'lateralization',
        'projection_density', 'projection_energy', 'projection_volume',
        'volume', 'is_injection',
        'gender', 'strain', 'injection_volume'
        , 'injection_z'
    ]
    
    final_df = unionizes[cols_to_keep].copy()

    # 7. Save
    output_dir = ANALYSIS_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{seed}_full_analysis.csv"
    
    final_df.to_csv(output_file, index=False)
    log.info(f"[SUCCESS] Full analysis data saved to: {output_file}")
    log.info(f"First 5 rows:\n{final_df.head()}")

def main() -> int:
    run_analysis_mining()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
