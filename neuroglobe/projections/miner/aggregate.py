from fnmatch import fnmatchcase
from pathlib import Path

import pandas as pd

from neuroglobe.core.coordinates import Hemisphere, injection_hemisphere
from neuroglobe.core.provenance import (
    artifact_manifest,
    canonical_json_hash,
    file_sha256,
    write_json_atomic,
)
from neuroglobe.projections.config import load_mining_config
from neuroglobe.projections.definitions import CONFIGS_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
from neuroglobe.projections.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"

def load_config():
    return load_mining_config(CONFIG_PATH)

def download_and_aggregate(experiments_df, mcc, config):
    """
    Downloads numeric data (CSV) and 3D volume (Tracts) for the best experiment.
    """
    from neuroglobe.projections.miner.extract_tracts import fetch_and_process_tracts

    minimum_volume = config["quality_control"]["min_injection_volume"]
    if "injection_volume" not in experiments_df.columns:
        raise ValueError("Allen experiments are missing the injection_volume column.")
    eligible_experiments = experiments_df[
        experiments_df["injection_volume"].fillna(0) >= minimum_volume
    ].copy()
    excluded_ids = sorted(
        set(experiments_df["id"].astype(int)) - set(eligible_experiments["id"].astype(int))
    )
    if eligible_experiments.empty:
        raise ValueError(
            f"No experiment passed min_injection_volume={minimum_volume} mm3."
        )
    if excluded_ids:
        log.info("[QC] Excluded experiment IDs below volume threshold: %s", excluded_ids)

    experiment_ids = eligible_experiments["id"].tolist()
    metric = config["processing"]["metric"]
    agg_mode = config["processing"]["aggregation_mode"]
    
    # --- 1. Select "Best Experiment" for Tractography ---
    # Sort by injection volume descending and take the first one.
    if not eligible_experiments.empty:
        best_exp = eligible_experiments.sort_values(
            by=["injection_volume", "id"], ascending=[False, True]
        ).iloc[0]
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
    final_df = process_aggregation(
        unionizes,
        eligible_experiments,
        id_to_acronym,
        metric,
        agg_mode,
        best_id,
        primary_seed=config["experiment"]["seed_acronym"],
        target_pattern=config["experiment"]["target_regex"],
        threshold_lower=config["quality_control"]["threshold_lower"],
    )
    final_df.attrs["included_experiment_ids"] = [int(value) for value in experiment_ids]
    final_df.attrs["excluded_experiment_ids"] = excluded_ids
    
    return final_df

def process_aggregation(
    unionizes,
    experiments_df,
    id_to_acronym,
    metric,
    agg_mode,
    best_id=None,
    *,
    primary_seed=None,
    target_pattern="*",
    threshold_lower=0.0,
):
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
    
    # Allen coordinates use x=AP, y=DV, z=ML. Laterality must use injection_z.
    if not experiments_df.empty and "injection_z" in experiments_df.columns:
        exp_id_to_ml = dict(zip(experiments_df["id"], experiments_df["injection_z"]))
    else:
        exp_id_to_ml = {}

    valid_df["inj_hemi"] = valid_df["experiment_id"].map(
        lambda experiment_id: injection_hemisphere(exp_id_to_ml.get(experiment_id))
    )
    
    # Calculate Ipsi/Contra
    # If projection_hemisphere (hemisphere_id) == inj_hemi -> Ipsi
    valid_df["is_ipsi"] = valid_df.apply(
        lambda row: row["inj_hemi"] is not None
        and int(row["hemisphere_id"]) == int(row["inj_hemi"]),
        axis=1,
    )
    valid_df["is_contra"] = valid_df.apply(
        lambda row: row["inj_hemi"] is not None
        and int(row["hemisphere_id"]) in (Hemisphere.LEFT, Hemisphere.RIGHT)
        and int(row["hemisphere_id"]) != int(row["inj_hemi"]),
        axis=1,
    )

    # Separate Seed and Targets
    seed_df = valid_df[valid_df['is_injection'] == True].copy()
    target_df = valid_df[valid_df["is_injection"] == False].copy()
    target_df = target_df[
        target_df["acronym"].map(lambda value: fnmatchcase(str(value), target_pattern))
    ]
    if primary_seed:
        target_df = target_df[target_df["acronym"] != primary_seed]
    
    # --- 5. Aggregation (Targets) ---
    log.info(f"[MINER] Aggregating targets using mode: '{agg_mode}'...")
    
    # Aggregation helper
    def agg_func(df, col):
        if df.empty: return pd.Series(dtype=float)
        if agg_mode == 'mean': return df.groupby('acronym')[col].mean()
        elif agg_mode == 'median': return df.groupby('acronym')[col].median()
        elif agg_mode == 'max': return df.groupby('acronym')[col].max()
        return df.groupby('acronym')[col].mean()

    # Ipsilateral and contralateral exclude unknown/midline injections.
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
    
    # Mean is defined as the arithmetic mean of independently aggregated
    # left/right values. Hemisphere ID 3 is not mixed into this statistic.
    final_df = pd.DataFrame({
        'value_ipsi': s_ipsi,
        'value_contra': s_contra,
        'value_left': s_left,
        'value_right': s_right
    })
    final_df = final_df.fillna(0)
    final_df["value_mean"] = (
        final_df["value_left"] + final_df["value_right"]
    ) / 2.0
    value_columns = [
        "value_mean",
        "value_ipsi",
        "value_contra",
        "value_left",
        "value_right",
    ]
    final_df[value_columns] = final_df[value_columns].mask(
        final_df[value_columns] < float(threshold_lower), 0.0
    )
    final_df = final_df.reset_index()
    
    # Legacy compatibility: 'value' column = 'value_mean'
    final_df['value'] = final_df['value_mean']
    final_df['is_seed'] = False
    
    # --- 6. Handle Seed ---
    # For seed, we usually just take the max value as reference
    seed_rows = []
    if primary_seed and primary_seed in set(seed_df["acronym"]):
        seed_acronym = primary_seed
    elif not seed_df.empty:
        seed_acronym = str(seed_df["acronym"].value_counts().index[0])
    else:
        seed_acronym = None
    if seed_acronym is not None:
        # Determine max value for seed (usually saturation)
        val = seed_df[seed_df["acronym"] == seed_acronym][metric].max()
        seed_rows.append({
            'acronym': seed_acronym,
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

def main() -> int:
    from neuroglobe.projections.miner.fetch import get_experiments

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

    manifest = artifact_manifest(
        artifact_type="projection_connectivity_csv",
        coordinate_convention="Allen CCF: x=AP, y=DV, z=ML; units=um",
        config=config,
        config_hash=canonical_json_hash(config),
        included_experiment_ids=final_data.attrs.get("included_experiment_ids", []),
        excluded_experiment_ids=final_data.attrs.get("excluded_experiment_ids", []),
        representative_experiment_id=int(final_data["tract_experiment_id"].iloc[0])
        if "tract_experiment_id" in final_data.columns and not final_data.empty
        else None,
        outputs={
            output_path.name: file_sha256(output_path),
        },
    )
    write_json_atomic(
        output_path.with_suffix(".manifest.json"),
        manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
