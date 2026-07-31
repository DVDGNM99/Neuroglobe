import logging
import sys
from datetime import datetime
from neuroglobe.projections.definitions import LOGS_DIR

def setup_logger(name: str = "Neuroglobe", *, file_logging: bool = False):
    """
    Sets up a logger that matches the audit requirements:
    - Writes to file (filtered by robust path)
    - Writes to console
    - Standardized formatting
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # Console logging is safe at import time and works in read-only environments.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)

    logger.addHandler(console_handler)

    if file_logging:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        file_handler = logging.FileHandler(
            LOGS_DIR / f"app_{timestamp}.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    return logger

# Default logging has no filesystem side effects.
log = setup_logger()
