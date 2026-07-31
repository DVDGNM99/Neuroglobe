from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPOSITORY_ROOT / "genetics"

# Standard Directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

CONFIGS_DIR = PROJECT_ROOT / "configs"
LOGS_DIR = PROJECT_ROOT / "logs"
RUNTIME_DIR = PROJECT_ROOT / "runtime"

# Hardware/Atlas Constants
ATLAS_RESOLUTION = (25.0, 25.0, 25.0)  # micrometres


def ensure_runtime_directories() -> None:
    for directory in (LOGS_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, RUNTIME_DIR):
        directory.mkdir(parents=True, exist_ok=True)
