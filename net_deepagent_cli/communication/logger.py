import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logger(name: str, log_file: Optional[str] = None, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create file handler
    if log_file:
        # Resolve path relative to home or current dir? 
        # Plan mentioned ~/.net-deepagent/<agent_name>/... for other things.
        # Let's put it in the current workspace or a dedicated log dir.
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Default logger for the communication module
# We'll use a file named communication.log in the project root for now, or in a logs dir.
project_root = Path(__file__).parent.parent.parent
comm_logger = setup_logger("communication", log_file=str(project_root / "logs" / "communication.log"))
