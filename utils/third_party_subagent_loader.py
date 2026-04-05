"""
third_party_subagent_loader.py
------------------------------
Discovers and loads user-defined ("third-party") subagent plugin definitions
from:

    ~/.net-deepagent/net-agent/subagents/<agent-name>/agent.json

Each agent.json is a declarative spec that is converted into a plain dict
compatible with ``create_deep_agent()``'s ``subagents`` argument.

Intended use (inside ``create_network_agent()`` in net_deepagent.py)::

    from utils.third_party_subagent_loader import load_third_party_subagents

    third_party = load_third_party_subagents(
        all_mcp_tools=tools,
        available_models=AVAILABLE_MODELS,
        builtin_tools={
            "search_internet": search_internet,
            "user_clarification_and_action_tool": user_clarification_and_action_tool,
        },
    )
    subagents.extend(third_party)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("third_party_subagent_loader")

# Base directory for all net-agent user data
_NET_AGENT_DIR = Path.home() / ".net-deepagent" / "net-agent"

# Required fields every agent.json must contain
_REQUIRED_FIELDS = ("name", "description", "system_prompt")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_third_party_subagents_dir() -> Path:
    """Return the canonical path where third-party subagent folders live.

    Returns:
        Path: ``~/.net-deepagent/net-agent/subagents/``
    """
    return _NET_AGENT_DIR / "subagents"


def load_third_party_subagents(
    all_mcp_tools: List[Any],
    available_models: Dict[str, Any],
    builtin_tools: Optional[Dict[str, Any]] = None,
    default_model_key: str = "gpt-5-mini",
) -> List[Dict[str, Any]]:
    """Discover and load all enabled third-party subagent definitions.

    Walks ``~/.net-deepagent/net-agent/subagents/*/agent.json``, parses each
    file, validates required fields, resolves tools / skills / model, and
    returns a list of agent dicts ready to be appended to the main
    ``subagents`` list in ``create_network_agent()``.

    Any agent that fails validation or JSON parsing is *skipped with a warning*
    — it will never crash the main agent startup.

    Args:
        all_mcp_tools:    Full list of tools obtained from all MCP servers.
        available_models: The ``AVAILABLE_MODELS`` dict from net_deepagent.py.
        builtin_tools:    Map of built-in tool name → tool object.
                          Recognised keys: ``"search_internet"``,
                          ``"user_clarification_and_action_tool"``.
        default_model_key: Key to fall back to when ``model`` is absent or
                           unrecognised in ``available_models``.

    Returns:
        List of agent dicts (may be empty if directory does not exist or no
        valid agent is found).
    """
    builtin_tools = builtin_tools or {}
    subagents_dir = get_third_party_subagents_dir()

    if not subagents_dir.exists() or not subagents_dir.is_dir():
        logger.info(
            "Third-party subagents directory not found: %s — skipping.", subagents_dir
        )
        return []

    loaded: List[Dict[str, Any]] = []

    for agent_dir in sorted(subagents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue

        agent_json_path = agent_dir / "agent.json"
        if not agent_json_path.exists():
            logger.debug("No agent.json in %s — skipping.", agent_dir)
            continue

        agent_dict = _load_single_agent(
            agent_json_path=agent_json_path,
            all_mcp_tools=all_mcp_tools,
            available_models=available_models,
            builtin_tools=builtin_tools,
            default_model_key=default_model_key,
        )
        if agent_dict is not None:
            loaded.append(agent_dict)
            logger.info("Loaded third-party subagent: '%s'", agent_dict["name"])

    logger.info(
        "Third-party subagent loader: %d agent(s) loaded from %s",
        len(loaded),
        subagents_dir,
    )
    return loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_single_agent(
    agent_json_path: Path,
    all_mcp_tools: List[Any],
    available_models: Dict[str, Any],
    builtin_tools: Dict[str, Any],
    default_model_key: str,
) -> Optional[Dict[str, Any]]:
    """Parse and validate one agent.json.  Returns None on any error."""

    # --- Parse JSON ---
    try:
        with agent_json_path.open("r", encoding="utf-8") as fh:
            spec: Dict[str, Any] = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Skipping %s — failed to parse JSON: %s", agent_json_path, exc
        )
        return None

    # --- Check enabled flag (default True) ---
    if not spec.get("enabled", True):
        logger.info("Skipping disabled agent at %s", agent_json_path)
        return None

    # --- Validate required fields ---
    for field in _REQUIRED_FIELDS:
        if not spec.get(field):
            logger.warning(
                "Skipping %s — missing required field '%s'.", agent_json_path, field
            )
            return None

    # --- Resolve tools ---
    tools = _resolve_tools(
        spec=spec,
        all_mcp_tools=all_mcp_tools,
        builtin_tools=builtin_tools,
    )

    # --- Resolve skills ---
    skills = _resolve_skills(spec, agent_json_path)

    # --- Resolve model ---
    model_key = spec.get("model", default_model_key)
    if model_key not in available_models:
        logger.warning(
            "Agent '%s': model key '%s' not found in AVAILABLE_MODELS; "
            "falling back to '%s'.",
            spec["name"],
            model_key,
            default_model_key,
        )
        model_key = default_model_key

    model = available_models.get(model_key)

    # --- Build agent dict ---
    agent: Dict[str, Any] = {
        "name": spec["name"],
        "description": spec["description"],
        "system_prompt": spec["system_prompt"],
        "tools": tools,
    }

    if model is not None:
        agent["model"] = model

    if skills:
        agent["skills"] = skills

    return agent


def _resolve_tools(
    spec: Dict[str, Any],
    all_mcp_tools: List[Any],
    builtin_tools: Dict[str, Any],
) -> List[Any]:
    """Build the tool list for an agent from its spec."""
    tool_filter: Dict[str, Any] = spec.get("tool_filter", {})
    prefixes: List[str] = tool_filter.get("prefixes", [])
    exact_names: List[str] = tool_filter.get("names", [])
    categories: List[str] = tool_filter.get("categories", [])

    resolved: List[Any] = []
    seen_names: set = set()

    def _add(t: Any) -> None:
        if t.name not in seen_names:
            seen_names.add(t.name)
            resolved.append(t)

    # Filter from MCP pool by prefix
    for t in all_mcp_tools:
        if any(t.name.lower().startswith(p.lower()) for p in prefixes):
            _add(t)

    # Filter from MCP pool by exact name
    for t in all_mcp_tools:
        if t.name in exact_names:
            _add(t)

    # Filter from MCP pool by category (reuse existing helper)
    if categories:
        # Import the helper so we don't duplicate the category logic
        try:
            from net_deepagent import filter_tools_by_category
            for cat in categories:
                for t in filter_tools_by_category(all_mcp_tools, cat):
                    _add(t)
        except ImportError:
            logger.warning(
                "Could not import filter_tools_by_category from net_deepagent; "
                "category filtering skipped."
            )

    # Add named built-in tools
    for tool_name in spec.get("include_tools", []):
        if tool_name in builtin_tools:
            t = builtin_tools[tool_name]
            if t.name not in seen_names:
                seen_names.add(t.name)
                resolved.append(t)
        else:
            logger.warning(
                "Agent '%s': built-in tool '%s' not found in builtin_tools map.",
                spec.get("name", "?"),
                tool_name,
            )

    return resolved


def _resolve_skills(
    spec: Dict[str, Any], agent_json_path: Path
) -> List[str]:
    """Expand and validate skill directory paths from the spec.

    Each entry in ``spec["skills"]`` must be an absolute path (after ``~``
    expansion) that contains a ``SKILL.md`` file.  Invalid paths are logged
    and skipped — they do NOT prevent the agent from loading.

    Returns:
        List of validated, absolute skill directory path strings (with
        trailing ``/`` to match the convention used by ``get_network_skills``).
    """
    raw_skills: List[str] = spec.get("skills", [])
    if not raw_skills:
        return []

    valid: List[str] = []
    for raw in raw_skills:
        skill_path = Path(raw).expanduser().resolve()
        if not skill_path.is_dir():
            logger.warning(
                "Agent '%s' skill path does not exist or is not a directory: %s — skipped.",
                spec.get("name", "?"),
                raw,
            )
            continue
        if not (skill_path / "SKILL.md").exists():
            logger.warning(
                "Agent '%s' skill path has no SKILL.md: %s — skipped.",
                spec.get("name", "?"),
                raw,
            )
            continue
        # Append trailing slash to match the convention in get_network_skills()
        valid.append(str(skill_path) + "/")
        logger.debug(
            "Agent '%s': resolved skill '%s'",
            spec.get("name", "?"),
            skill_path,
        )

    return valid
