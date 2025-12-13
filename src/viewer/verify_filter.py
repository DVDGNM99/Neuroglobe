
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

try:
    from src.viewer import filter_tracts
    from src.logger_config import log
    log.info("Import successful.")
    
    # Check if DATA_DIR is accessible
    log.info(f"Data Dir: {filter_tracts.DATA_DIR}")
    
    log.info("Filter Tracts module verification passed.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
