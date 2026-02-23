"""
registry_manager.py
-------------------
Utility helpers for reading and writing the A2A agents registry JSON file.

The registry format is a simple flat dict:
    { "<agent-name>": "<base-url>", ... }

All functions are synchronous so they can be called from both sync and async
contexts without extra ceremony.
"""

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Default registry path (relative to the a2a_capability package)
_DEFAULT_REGISTRY = Path(__file__).parent / "agents_registry.json"


def get_default_registry_path() -> Path:
    """Return the default registry file path."""
    return _DEFAULT_REGISTRY


def load_registry(path: Path | None = None) -> Dict[str, str]:
    """
    Load the agents registry from disk.

    Args:
        path: Path to the registry JSON file. Defaults to the package registry.

    Returns:
        Dict mapping agent name -> base URL.  Empty dict if file missing.
    """
    target = path or _DEFAULT_REGISTRY
    if not target.exists():
        logger.warning(f"Registry file not found at {target}. Returning empty registry.")
        return {}
    try:
        with open(target, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error(f"Registry file {target} is not a JSON object. Returning empty registry.")
            return {}
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse registry file {target}: {e}")
        return {}


def save_registry(registry: Dict[str, str], path: Path | None = None) -> None:
    """
    Persist the registry dict to disk as a formatted JSON file.

    Args:
        registry: Dict mapping agent name -> base URL.
        path: Target file path. Defaults to the package registry.
    """
    target = path or _DEFAULT_REGISTRY
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        json.dump(registry, f, indent=4)
    logger.info(f"Registry saved to {target} ({len(registry)} agents)")


def add_agent(name: str, url: str, path: Path | None = None) -> None:
    """
    Add (or update) an agent entry in the registry.

    Args:
        name: Agent identifier key (e.g. 'dns_deepagent').
        url:  Base URL of the agent (e.g. 'http://localhost:8003').
        path: Optional override for the registry file path.
    """
    registry = load_registry(path)
    registry[name] = url
    save_registry(registry, path)
    logger.info(f"Agent '{name}' added/updated in registry → {url}")


def remove_agent(name: str, path: Path | None = None) -> bool:
    """
    Remove an agent entry from the registry.

    Args:
        name: Agent identifier key to remove.
        path: Optional override for the registry file path.

    Returns:
        True if the agent was found and removed, False if it didn't exist.
    """
    registry = load_registry(path)
    if name not in registry:
        logger.warning(f"Agent '{name}' not found in registry.")
        return False
    del registry[name]
    save_registry(registry, path)
    logger.info(f"Agent '{name}' removed from registry.")
    return True
