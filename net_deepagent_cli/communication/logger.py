import logging
import sys
import os
from pathlib import Path
from typing import Optional

DEFAULT_LOG_DIR = Path.home() / ".net_deepagent" / "logs"

# Global variable to hold the log file for the current process/session
_PROCESS_LOG_FILE: Optional[Path] = None

def set_process_log_file(log_file: str):
    """
    Sets a unified log file for the current process.
    All subsequent calls to setup_logger without an explicit log_file will use this.
    Also configures the root logger to catch all unconfigured module logs.
    """
    global _PROCESS_LOG_FILE
    path = Path(log_file)
    if not path.is_absolute():
        path = DEFAULT_LOG_DIR / path
    _PROCESS_LOG_FILE = path
    
    # Ensure directory exists immediately
    _PROCESS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger to ensure all libraries find a sane default
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Root Console Handler
    root_console_handler = logging.StreamHandler(sys.stdout)
    root_console_handler.setFormatter(formatter)
    root_logger.addHandler(root_console_handler)

    # Root File Handler
    try:
        root_file_handler = logging.FileHandler(str(_PROCESS_LOG_FILE))
        root_file_handler.setFormatter(formatter)
        root_logger.addHandler(root_file_handler)
    except Exception as e:
        print(f"Warning: Could not setup root file logging at {_PROCESS_LOG_FILE}: {e}")

def setup_logger(name: str, log_file: Optional[str] = None, level=logging.INFO):
    """
    Function to setup a logger. 
    Priority for file destination:
    1. Explicit log_file argument
    2. Global _PROCESS_LOG_FILE (if set)
    3. Default to name.log in DEFAULT_LOG_DIR
    """
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Disable propagation to root to avoid double logging
    # Root already handles console/file if set_process_log_file was called
    logger.propagate = False
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create console handler (screen stream)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Determine final log path
    final_path: Path
    if log_file is not None:
        # Explicit override
        path = Path(log_file)
        final_path = path if path.is_absolute() else DEFAULT_LOG_DIR / path
    elif _PROCESS_LOG_FILE is not None:
        # Use child/shared process log
        final_path = _PROCESS_LOG_FILE
    else:
        # Fallback to module-specific default
        final_path = DEFAULT_LOG_DIR / f"{name.replace('.', '_')}.log"

    # Create file handler
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(str(final_path))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Use print as backup if logging setup fails
        print(f"Warning: Could not setup file logging at {final_path}: {e}")

    return logger

# Default logger for the communication module
# Initially setup, but will follow the process log if set later
comm_logger = setup_logger("communication")
