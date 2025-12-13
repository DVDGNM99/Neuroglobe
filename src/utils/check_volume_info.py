import sys
from pathlib import Path
from vedo import Volume

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.logger_config import log

def check_volume(path):
    log.info(f"--- Volume Info: {path} ---")
    try:
        vol = Volume(path)
        log.info(f"Dimensions:   {vol.dimensions()}")
        log.info(f"Spacing:      {vol.spacing()}")
        log.info(f"Origin:       {vol.origin()}")
        log.info(f"Bounds:       {vol.bounds()}")
        log.info(f"Scalar Range: {vol.scalar_range()}")
        log.info("-----------------------------")
    except Exception as e:
        log.error(f"Error loading volume: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log.error("Usage: python check_volume_info.py <path_to_nrrd>")
    else:
        check_volume(sys.argv[1])
