from pathlib import Path

# Repository paths are explicit; importing this module does not create files.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPOSITORY_ROOT / "projections"

# Standard Directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TRACTS_DIR = PROCESSED_DATA_DIR / "tracts"

CONFIGS_DIR = PROJECT_ROOT / "configs"
SCENES_DIR = PROJECT_ROOT / "scenes"
LOGS_DIR = PROJECT_ROOT / "logs"

# Hardware/Atlas Constants
ATLAS_RESOLUTION = (25.0, 25.0, 25.0)  # micrometres


def ensure_runtime_directories() -> None:
    for directory in (LOGS_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, TRACTS_DIR, SCENES_DIR):
        directory.mkdir(parents=True, exist_ok=True)
