"""
agents_ui.py
------------
Handlers for the `/agents` sub-commands in the net_deepagent_cli.

Commands:
    /agents list                   — display registry + live status
    /agents add <name> <url>       — persist to registry and load live
    /agents remove <name>          — remove from registry AND unload from session
    /agents unload <name>          — unload from session only (keeps registry)
    /agents load                   — rebind all registered A2A tools to the agent
"""

import logging
from pathlib import Path
from typing import Any, List

from rich.table import Table

from a2a_capability.registry_manager import (
    get_default_registry_path,
    load_registry,
    add_agent as registry_add,
    remove_agent as registry_remove,
)

logger = logging.getLogger(__name__)


def _get_registry_path() -> Path:
    """Resolve the registry file path."""
    return get_default_registry_path()


# ---------------------------------------------------------------------------
# /agents list
# ---------------------------------------------------------------------------

async def handle_agents_list(parts: List[str], ui: Any, agent: Any) -> None:
    """Display all registered agents with their live online/offline status."""
    registry_path = _get_registry_path()
    registry = load_registry(registry_path)

    if not registry:
        ui.print_message(
            f"No agents in registry. Use [bold cyan]/agents add <name> <url>[/bold cyan] to add one.",
            role="system",
        )
        return

    # Determine which agents are live in the current session
    live_agents: set = set()
    if agent is not None and hasattr(agent, "a2a_middleware"):
        live_agents = set(agent.a2a_middleware.remote_agents.keys())

    table = Table(title="A2A Agent Registry", border_style="blue")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("URL", style="white")
    table.add_column("Registry", style="dim green")
    table.add_column("Session", style="white")

    for name, url in registry.items():
        in_session = name in live_agents
        session_status = "[bold green]Loaded[/bold green]" if in_session else "[dim]Unloaded[/dim]"
        table.add_row(name, url, "✓", session_status)

    ui.console.print(table)
    ui.console.print(
        "[dim]'Loaded' = tool available to the agent this session. "
        "Use [bold cyan]/agents load[/bold cyan] to reload all registry entries.[/dim]"
    )


# ---------------------------------------------------------------------------
# /agents add <name> <url>
# ---------------------------------------------------------------------------

async def handle_agents_add(parts: List[str], ui: Any, agent: Any) -> None:
    """
    /agents add <name> <url>
    Persist the agent to the registry and register it with the live middleware.
    """
    if len(parts) < 4:
        ui.print_message(
            "Usage: [bold cyan]/agents add <name> <url>[/bold cyan]\n"
            "Example: /agents add dns_deepagent http://localhost:8003",
            role="error",
        )
        return

    name = parts[2].strip()
    url = parts[3].strip()

    # Basic URL sanity check
    if not (url.startswith("http://") or url.startswith("https://")):
        ui.print_message(
            f"Invalid URL [bold red]{url}[/bold red]. Must start with http:// or https://",
            role="error",
        )
        return

    # 1. Persist to registry
    try:
        registry_path = _get_registry_path()
        registry_add(name, url, registry_path)
        ui.print_message(
            f"Agent [bold cyan]{name}[/bold cyan] → [white]{url}[/white] saved to registry. ✓",
            role="system",
        )
    except Exception as e:
        ui.print_message(f"Failed to save to registry: {e}", role="error")
        return

    # 2. Register with the running middleware (best-effort — agent may be offline)
    if agent is not None and hasattr(agent, "a2a_middleware"):
        ui.print_message(f"Connecting to agent at [white]{url}[/white]…", role="system")
        try:
            await agent.a2a_middleware.register_remote_agent(name, url)
            if name in agent.a2a_middleware.remote_agents:
                ui.print_message(
                    f"[bold green]✓ Agent [bold cyan]{name}[/bold cyan] is online and loaded into this session.[/bold green]",
                    role="system",
                )
            else:
                ui.print_message(
                    f"[yellow]⚠ Agent [bold cyan]{name}[/bold cyan] was saved but could not be reached (offline?).\n"
                    f"  It will be reconnected on next startup or use [bold cyan]/agents load[/bold cyan].[/yellow]",
                    role="system",
                )
        except Exception as e:
            ui.print_message(
                f"[yellow]⚠ Agent saved to registry but failed to load live: {e}[/yellow]",
                role="system",
            )
    else:
        ui.print_message(
            "Agent saved to registry. No running middleware found — restart to load.",
            role="system",
        )


# ---------------------------------------------------------------------------
# /agents remove <name>
# ---------------------------------------------------------------------------

async def handle_agents_remove(parts: List[str], ui: Any, agent: Any) -> None:
    """
    /agents remove <name>
    Remove the agent from the registry AND unload it from the live session.
    """
    if len(parts) < 3:
        ui.print_message(
            "Usage: [bold cyan]/agents remove <name>[/bold cyan]",
            role="error",
        )
        return

    name = parts[2].strip()

    # 1. Remove from registry
    registry_path = _get_registry_path()
    removed = registry_remove(name, registry_path)

    if removed:
        ui.print_message(
            f"Agent [bold cyan]{name}[/bold cyan] removed from registry. ✓",
            role="system",
        )
    else:
        ui.print_message(
            f"Agent [bold red]{name}[/bold red] not found in registry.",
            role="error",
        )
        # Still attempt to unload from session in case it was loaded manually
        # (fall through to session unload below)

    # 2. Unload from running session
    _unload_from_session(name, agent, ui)


# ---------------------------------------------------------------------------
# /agents unload <name>
# ---------------------------------------------------------------------------

async def handle_agents_unload(parts: List[str], ui: Any, agent: Any) -> None:
    """
    /agents unload <name>
    Remove the agent from the running session only. Registry is untouched.
    """
    if len(parts) < 3:
        ui.print_message(
            "Usage: [bold cyan]/agents unload <name>[/bold cyan]",
            role="error",
        )
        return

    name = parts[2].strip()
    _unload_from_session(name, agent, ui)
    ui.print_message(
        f"Registry entry for [bold cyan]{name}[/bold cyan] is preserved. "
        f"Use [bold cyan]/agents load[/bold cyan] to reload it.",
        role="system",
    )


# ---------------------------------------------------------------------------
# /agents load
# ---------------------------------------------------------------------------

async def handle_agents_load(parts: List[str], ui: Any, agent: Any) -> None:
    """
    /agents load
    Re-register all agents from the registry into the running middleware,
    then rebuild the A2A tool bindings.
    """
    if agent is None or not hasattr(agent, "a2a_middleware"):
        ui.print_message("No A2A middleware found on the running agent.", role="error")
        return

    registry_path = _get_registry_path()
    registry = load_registry(registry_path)

    if not registry:
        ui.print_message("Registry is empty — nothing to load.", role="system")
        return

    ui.print_message(
        f"Loading [bold]{len(registry)}[/bold] agent(s) from registry…",
        role="system",
    )

    loaded, failed = [], []
    for name, url in registry.items():
        try:
            await agent.a2a_middleware.register_remote_agent(name, url)
            if name in agent.a2a_middleware.remote_agents:
                loaded.append(name)
            else:
                failed.append((name, "Agent unreachable"))
        except Exception as e:
            failed.append((name, str(e)))

    # Rebuild tools cache
    agent.a2a_middleware._tools_cache = None  # force regeneration on next .tools access

    if loaded:
        ui.print_message(
            f"[bold green]✓ Loaded: {', '.join(loaded)}[/bold green]",
            role="system",
        )
    if failed:
        for fname, reason in failed:
            ui.print_message(
                f"[yellow]⚠ Could not load [bold cyan]{fname}[/bold cyan]: {reason}[/yellow]",
                role="system",
            )

    ui.print_message(
        "[dim]Note: Newly loaded A2A tools are available via the middleware. "
        "The main agent LLM will pick them up on the next invocation.[/dim]",
        role="system",
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _unload_from_session(name: str, agent: Any, ui: Any) -> None:
    """Remove an agent from the running middleware (session only)."""
    if agent is None or not hasattr(agent, "a2a_middleware"):
        ui.print_message("No running A2A middleware found.", role="system")
        return

    middleware = agent.a2a_middleware
    if name in middleware.remote_agents:
        del middleware.remote_agents[name]
        middleware._tools_cache = None  # force tools cache rebuild
        ui.print_message(
            f"Agent [bold cyan]{name}[/bold cyan] unloaded from this session. ✓",
            role="system",
        )
    else:
        ui.print_message(
            f"Agent [bold yellow]{name}[/bold yellow] was not active in this session.",
            role="system",
        )
