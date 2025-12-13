
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

try:
    from src.miner import miner_analysis
    from src.logger_config import log
    log.info("Import successful.")
    
    # Check if CONFIG_PATH is accessible
    log.info(f"Config Path: {miner_analysis.CONFIG_PATH}")
    
    log.info("Miner Analysis module verification passed.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
