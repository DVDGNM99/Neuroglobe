
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

try:
    from src.viewer import logic
    from src.logger_config import log
    log.info("Import successful.")
    
    # Test hex_to_rgb
    rgb = logic.hex_to_rgb("#FFFFFF")
    log.info(f"Hex to RGB: {rgb}")
    assert rgb == [255, 255, 255]
    
    log.info("Logic module verification passed.")
except Exception as e:
    # Use print for fallback, or assume src.logger is available 
    # but if import fails, we can't use log.
    import traceback
    traceback.print_exc()
    sys.exit(1)
