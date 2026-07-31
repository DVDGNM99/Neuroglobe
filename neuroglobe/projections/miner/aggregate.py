from fnmatch import fnmatchcase
from pathlib import Path

import pandas as pd

from neuroglobe.core.coordinates import Hemisphere, injection_hemisphere
from neuroglobe.core.provenance import (
    artifact_manifest,
    canonical_json_hash,
    file_record,
    file_sha256,
    run_manifest,
    write_json_atomic,
    write_json_immutable,
)
from neuroglobe.projections.config import load_mining_config
from neuroglobe.projections.definitions import CONFIGS_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
from neuroglobe.projections.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"

def load_config():
    return load_mining_config(CONFIG_PATH)


def select_representative_experiment(experiments_df: pd.DataFrame) -> pd.Series:
    """Select a 3D representative using volume and coordinate completeness.

    Injection volume contributes 75% of the score.  Availability of AP/DV/ML
    coordinates contributes 25%, preventing a large but spatially incomplete
    experiment from silently becoming the anatomical representative.
    """

    required = {"id", "injection_volume"}
    missing = required - set(experiments_df.columns)
    if missing:
        raise ValueError(f"Representative selection is missing columns: {sorted(missing)}")
    if experiments_df.empty:
        raise ValueError("Cannot select a representative from an empty table.")

    scored = experiments_df.copy()
    volumes = pd.to_numeric(scored["injection_volume"], errors="coerce").fillna(0.0)
    maximum_volume = float(volumes.max())
    scored["volume_score"] = volumes / maximum_volume if maximum_volume > 0 else 0.0
    coordinate_columns = [
        column for column in ("injection_x", "injection_y", "injection_z")
        if column in scored.columns
    ]
    if coordinate_columns:
        scored["coordinate_completeness"] = scored[coordinate_columns].notna().mean(axis=1)
    else:
        scored["coordinate_completeness"] = 1.0
    scored["representative_score"] = (
        0.75 * scored["volume_score"] + 0.25 * scored["coordinate_completeness"]
    )
    return scored.sort_values(
        by=["representative_score", "injection_volume", "id"],
        ascending=[False, False, True],
    ).iloc[0]


def _summarize_values(
    frame: pd.DataFrame,
    metric: str,
    aggregation_mode: str,
    suffix: str,
) -> pd.DataFrame:
    """Summarize independent experiment values with uncertainty columns."""

    columns = [
        "acronym",
        f"value_{suffix}",
        f"n_{suffix}",
        f"variance_{suffix}",
        f"std_{suffix}",
        f"ci95_low_{suffix}",
        f"ci95_high_{suffix}",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    per_experiment = (
        frame.groupby(["experiment_id", "acronym"], as_index=False)[metric].mean()
    )
    grouped = per_experiment.groupby("acronym")[metric]
    descriptive = grouped.agg(["count", "mean", "var", "std"])
    if aggregation_mode == "median":
        central = grouped.median()
    elif aggregation_mode == "max":
        central = grouped.max()
    else:
        central = descriptive["mean"]
    standard_error = descriptive["std"] / descriptive["count"].pow(0.5)
    return pd.DataFrame(
        {
            "acronym": descriptive.index,
            f"value_{suffix}": central,
            f"n_{suffix}": descriptive["count"].astype(int),
            f"variance_{suffix}": descriptive["var"],
            f"std_{suffix}": descriptive["std"],
            f"ci95_low_{suffix}": descriptive["mean"] - 1.96 * standard_error,
            f"ci95_high_{suffix}": descriptive["mean"] + 1.96 * standard_error,
        }
    ).reset_index(drop=True)

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
    if not eligible_experiments.empty:
        best_exp = select_representative_experiment(eligible_experiments)
        best_id = int(best_exp['id'])
        log.info(f"[MINER] Selected Representative Experiment: {best_id}")
        log.info(f"        (Injection Vol: {best_exp['injection_volume']:.3f} mm3)")
        log.info(
            "        (Selection score: %.3f; coordinate completeness: %.2f)",
            best_exp["representative_score"],
            best_exp["coordinate_completeness"],
        )
        
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
    final_df.attrs["representative_selection"] = {
        "experiment_id": best_id,
        "score": float(best_exp["representative_score"]),
        "volume_score": float(best_exp["volume_score"]),
        "coordinate_completeness": float(best_exp["coordinate_completeness"]),
        "weights": {"injection_volume": 0.75, "coordinate_completeness": 0.25},
    }

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

    # Ipsilateral and contralateral exclude unknown/midline injections.  Each
    # animal is reduced first, so N and uncertainty describe independent
    # experiments rather than raw unionize row counts.
    df_ipsi = target_df[target_df['is_ipsi'] == True]
    df_contra = target_df[target_df['is_contra'] == True]
    df_left = target_df[target_df['hemisphere_id'] == 1]
    df_right = target_df[target_df['hemisphere_id'] == 2]

    side_values = target_df[target_df["hemisphere_id"].isin((1, 2))]
    per_side = side_values.pivot_table(
        index=["experiment_id", "acronym"],
        columns="hemisphere_id",
        values=metric,
        aggfunc="mean",
    )
    animal_means = per_side.mean(axis=1).rename(metric).reset_index()

    summaries = [
        _summarize_values(animal_means, metric, agg_mode, "mean"),
        _summarize_values(df_ipsi, metric, agg_mode, "ipsi"),
        _summarize_values(df_contra, metric, agg_mode, "contra"),
        _summarize_values(df_left, metric, agg_mode, "left"),
        _summarize_values(df_right, metric, agg_mode, "right"),
    ]
    final_df = summaries[0]
    for summary in summaries[1:]:
        final_df = final_df.merge(summary, on="acronym", how="outer")

    value_columns = [
        "value_mean",
        "value_ipsi",
        "value_contra",
        "value_left",
        "value_right",
    ]
    count_columns = [f"n_{suffix}" for suffix in ("mean", "ipsi", "contra", "left", "right")]
    for column in value_columns:
        final_df[column] = pd.to_numeric(final_df[column], errors="coerce").fillna(0.0)
    for column in count_columns:
        final_df[column] = (
            pd.to_numeric(final_df[column], errors="coerce").fillna(0).astype(int)
        )
    final_df[value_columns] = final_df[value_columns].mask(
        final_df[value_columns] < float(threshold_lower), 0.0
    )
    final_df = final_df.reset_index(drop=True)
    
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
            'value_contra': 0,
            'value_left': val,   # Simplified
            'value_right': val,  # Simplified
            'is_seed': True,
            'n_mean': int(
                seed_df[seed_df["acronym"] == seed_acronym]["experiment_id"].nunique()
            ),
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
            # 1. Keep requested targets that are not injection-site rows.
            # 2. Keep Primary Seed: The only allowed seed row.
            filtered_df = final_data[
                (final_data['acronym'].isin(custom_targets) & ~final_data['is_seed'])
                | (final_data['is_seed'] & (final_data['acronym'] == primary_seed))
            ]

            filtered_filename = f"{seed}_connectivity_filtered.csv"
            filtered_path = PROCESSED_DATA_DIR / filtered_filename
            filtered_df.to_csv(filtered_path, index=False)
            log.info(f"[SUCCESS] Filtered Data saved to: {filtered_path}")
            log.info(
                "          (Cleaned up %d spillover/unused regions)",
                len(final_data) - len(filtered_df),
            )

    if 'tract_experiment_id' in final_data.columns:
        log.info(
            "          Linked Tractography ID: %s",
            final_data['tract_experiment_id'].iloc[0],
        )

    output_paths = [output_path]
    if config.get("selection", {}).get("use_custom_targets", False) and "filtered_path" in locals():
        output_paths.append(filtered_path)
    run = run_manifest(
        "projection-connectivity-aggregation",
        parameters={
            "config": config,
            "included_experiment_ids": final_data.attrs.get("included_experiment_ids", []),
            "excluded_experiment_ids": final_data.attrs.get("excluded_experiment_ids", []),
            "representative_selection": final_data.attrs.get("representative_selection", {}),
        },
        outputs=[
            file_record(path, base_dir=PROCESSED_DATA_DIR, role="connectivity_csv")
            for path in output_paths
        ],
        atlas={"name": "Allen Mouse CCF", "resolution_um": [25, 25, 25]},
        transformations=[
            {"name": "Allen coordinate mapping", "version": 1, "axes": "x=AP,y=DV,z=ML"}
        ],
        packages=("allensdk", "pandas"),
    )
    run_path = PROCESSED_DATA_DIR / "runs" / f"{run['run_id']}.manifest.json"
    write_json_immutable(run_path, run)

    manifest = artifact_manifest(
        run_id=run["run_id"],
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
        run_manifest=run_path.relative_to(PROCESSED_DATA_DIR).as_posix(),
    )
    write_json_atomic(
        output_path.with_suffix(".manifest.json"),
        manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
