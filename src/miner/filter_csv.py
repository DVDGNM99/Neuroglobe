import sys
import yaml
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.definitions import CONFIGS_DIR, PROCESSED_DATA_DIR
from src.logger_config import log

CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"

def load_config():
    if not CONFIG_PATH.exists():
        log.error(f"Config not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def filter_csv(input_csv_path: str = None):
    config = load_config()
    seed_acronym = config.get("experiment", {}).get("seed_acronym", "")
    
    # 1. Auto-detect path if missing
    if not input_csv_path:
        log.info(f"No input file provided. Auto-detecting based on seed '{seed_acronym}'...")
        default_name = f"{seed_acronym}_connectivity.csv"
        input_csv_path = PROCESSED_DATA_DIR / default_name
    
    path = Path(input_csv_path)
    if not path.exists():
        log.error(f"Input CSV not found: {path}")
        return

    # 2. Get targets
    use_custom = config.get("selection", {}).get("use_custom_targets", False)
    custom_targets = config.get("selection", {}).get("custom_targets", [])
    
    if not use_custom:
        log.warning("Config 'use_custom_targets' is False. No filtering performed based on list.")
        return

    log.info(f"[FILTER] Filtering '{path.name}' for Seed '{seed_acronym}' + {len(custom_targets)} Targets...")

    # 3. Read CSV
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log.error(f"Error reading CSV: {e}")
        return

    # 4. Strict Filter Logic
    # - KEEP if acronym == seed_acronym
    # - KEEP if acronym in custom_targets
    # - FORCE is_seed=True ONLY for the strict seed
    
    # Normalize is_seed first
    if 'is_seed' not in df.columns:
        df['is_seed'] = False

    # Create mask
    mask_seed = (df['acronym'] == seed_acronym)
    mask_targets = (df['acronym'].isin(custom_targets))
    
    filtered_df = df[mask_seed | mask_targets].copy()
    
    # Force strict seed flag (fix "all black brain" issue)
    filtered_df['is_seed'] = (filtered_df['acronym'] == seed_acronym)

    # 5. Save
    output_filename = f"{path.stem}_filtered.csv"
    output_path = path.parent / output_filename
    
    filtered_df.to_csv(output_path, index=False)
    
    log.info(f"[SUCCESS] Filtered CSV saved to: {output_path}")
    log.info(f"          Rows kept: {len(filtered_df)} (Original: {len(df)})")
    log.info(f"          Targets: {filtered_df[filtered_df['is_seed']==False]['acronym'].tolist()}")

if __name__ == "__main__":
    # If arg provided, use it. Else None (triggers auto-detect)
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else None
    filter_csv(csv_arg)
