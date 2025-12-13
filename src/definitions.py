from pathlib import Path

# Robustly define the Project Root
# Assumes this file is in <PROJECT_ROOT>/src/definitions.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Standard Directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TRACTS_DIR = PROCESSED_DATA_DIR / "tracts"

CONFIGS_DIR = PROJECT_ROOT / "configs"
SCENES_DIR = PROJECT_ROOT / "scenes"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure logs/data directory exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Hardware/Atlas Constants
ATLAS_RESOLUTION = (25, 25, 25) # microns
