import logging
import sys
from datetime import datetime
from src.definitions import LOGS_DIR

def setup_logger(name="Neuroglobe"):
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

    # 1. File Handler (Detailed)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"app_{timestamp}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)


    # 2. Console Handler (User Friendly)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Create a default instance for easy import
log = setup_logger()
