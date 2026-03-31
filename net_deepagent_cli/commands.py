from typing import List, Optional
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
from net_deepagent_cli.agent import SkillsMiddleware
from net_deepagent_cli.config import AgentConfig
from langchain_core.messages import message_to_dict, messages_from_dict
from net_deepagent_cli.agents_ui import (
    handle_agents_list,
    handle_agents_add,
    handle_agents_remove,
    handle_agents_unload,
    handle_agents_load,
)
from net_deepagent_cli.automata_skills_ui import handle_skill_updates
from custom_middleware.skills_middleware import get_skill_learning_middleware
from net_deepagent_cli.skill_commands import (
    handle_skill_add,
    handle_skill_update,
)
import json
import datetime
import asyncio
from utils.session_archiver import fire_and_forget_archive

async def handle_command(command: str, ui, messages, agent=None):
    """Handle special slash commands"""
    parts = command.split()
    cmd = parts[0].lower()
    
    config_manager = AgentConfig(ui.agent_name)
    sessions_dir = config_manager.sessions_dir

    if cmd == "/help":
        table = Table(title="Available Commands", border_style="blue")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Subcommands", style="dim green")
        
        from net_deepagent_cli.ui import TerminalUI
        for command, info in TerminalUI.COMMAND_STRUCTURE.items():
            subs = info.get("subs", {})
            subs_str = ", ".join(subs.keys()) if subs else "-"
            table.add_row(command, info["desc"], subs_str)
            
        ui.console.print(table)
        ui.console.print("[dim]Tip: Type a command followed by a space to see subcommand suggestions.[/dim]")
    
    elif cmd == "/clear":
        messages.clear()
        ui.print_message("Conversation cleared", role="system")

    elif cmd == "/save":
        if not messages:
            ui.print_message("No context to save.", role="warning")
            return
            
        session_name = parts[1] if len(parts) > 1 else None
        if not session_name:
            session_name = await ui.prompt_simple("[bold blue]Enter session name to save:[/] ")
            if not session_name:
                return
        
        # Ensure .json extension
        if not session_name.endswith(".json"):
            filename = f"{session_name}.json"
        else:
            filename = session_name
            
        filepath = sessions_dir / filename
        
        try:
            # Serialize messages
            serialized_messages = [message_to_dict(m) for m in messages]
            with open(filepath, 'w') as f:
                json.dump(serialized_messages, f, indent=2)
            ui.print_message(f"Session saved to [bold cyan]{filename}[/bold cyan]", role="system")
            # Archive to ChromaDB asynchronously (fire-and-forget, non-blocking)
            fire_and_forget_archive(messages, session_name)
        except Exception as e:
            ui.print_message(f"Failed to save session: {e}", role="error")

    elif cmd == "/resume":
        await handle_resume_session(parts, ui, messages)

    elif cmd == "/sessions":
        available = list(sessions_dir.glob("*.json"))
        if not available:
            ui.print_message("No saved sessions found.", role="system")
            return
            
        table = Table(title="Saved Conversation Sessions", border_style="blue")
        table.add_column("Session Name", style="cyan")
        table.add_column("Messages", style="green")
        table.add_column("Last Modified", style="dim")
        table.add_column("Size", style="dim")
        
        for p in sorted(available, key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                size_kb = f"{p.stat().st_size / 1024:.1f} KB"
                with open(p, 'r') as f:
                    count = len(json.load(f))
                table.add_row(p.stem, str(count), mtime, size_kb)
            except:
                table.add_row(p.stem, "Error", "???", "???")
                
        ui.console.print(table)
    
    elif cmd == "/tokens":
        ui.console.print(Panel(
            f"[bold green]Session Token Usage:[/bold green]\n"
            f"[dim]Note: This tracks tokens from assistant responses in this session.[/dim]\n\n"
            f"[bold]Total Tokens:[/bold] {ui.total_tokens:,}",
            title="Token Usage",
            border_style="green"
        ))
        
    elif cmd == "/context":
        total_messages = len(messages)
        
        # Breakdown by type
        stats = {
            'human': {'count': 0, 'chars': 0},
            'ai': {'count': 0, 'chars': 0},
            'tool': {'count': 0, 'chars': 0},
            'system': {'count': 0, 'chars': 0},
            'other': {'count': 0, 'chars': 0}
        }
        
        for m in messages:
            m_type = getattr(m, 'type', 'other')
            if m_type not in stats:
                m_type = 'other'
                
            content = str(getattr(m, 'content', ''))
            # Also count tool_calls in AI messages as part of context size
            if m_type == 'ai' and hasattr(m, 'tool_calls'):
                content += str(m.tool_calls)
                
            stats[m_type]['count'] += 1
            stats[m_type]['chars'] += len(content)

        def est(chars): return chars // 4

        breakdown_text = ""
        for label, color, key in [
            ("User", "green", "human"),
            ("Assistant", "yellow", "ai"),
            ("Tool", "magenta", "tool"),
            ("System", "blue", "system")
        ]:
            if stats[key]['count'] > 0:
                breakdown_text += f"• [{color}]{label}:[/{color}] {stats[key]['count']} msgs (~{est(stats[key]['chars']):,} tokens)\n"

        total_est = est(sum(s['chars'] for s in stats.values()))
        
        ui.console.print(Panel(
            f"[bold cyan]Current Context Analysis:[/bold cyan]\n\n"
            f"{breakdown_text}\n"
            f" [bold]Total Estimated Depth:[/bold] ~{total_est:,} tokens\n"
            f" [dim](Estimation: ~4 chars per token)[/dim]",
            title="Context Status",
            border_style="cyan"
        ))
    
    elif cmd == "/skills":
        sub = parts[1].lower() if len(parts) > 1 else "list"

        if sub in ["add", "extract"]:
            if len(parts) < 3:
                ui.print_message("Usage: /skills add <doc_path> [skill_name]", role="error")
                return
            doc_path = parts[2]
            skill_name_hint = parts[3] if len(parts) > 3 else None
            await handle_skill_add(doc_path, skill_name_hint, ui.agent_name, ui)
            return

        elif sub == "update":
            # Parse: /skills update [skill_name] [source] [--dry-run]
            remaining = parts[2:]
            dry_run = "--dry-run" in remaining
            remaining = [p for p in remaining if p != "--dry-run"]

            skill_name = remaining[0] if len(remaining) > 0 else None
            source = remaining[1] if len(remaining) > 1 else None
            await handle_skill_update(skill_name, source, dry_run, ui.agent_name, ui, messages)
            return

        # List available skills
        skills_mw = SkillsMiddleware(ui.agent_name)
        skills = skills_mw.scan_skills()
        
        if not skills:
            ui.print_message("No skills found.", role="system")
        else:
            ui.console.print("[bold]Available Skills:[/bold]")
            for skill in skills:
                ui.console.print(f"  • [bold yellow]{skill['name']}[/bold yellow]: {skill['description']}")
                ui.console.print(f"    [dim]Path: {skill['path']}[/dim]")
    
    elif cmd == "/agents":
        sub = parts[1].lower() if len(parts) > 1 else "list"

        if sub == "list":
            await handle_agents_list(parts, ui, agent)
        elif sub == "add":
            await handle_agents_add(parts, ui, agent)
        elif sub == "remove":
            await handle_agents_remove(parts, ui, agent)
        elif sub == "unload":
            await handle_agents_unload(parts, ui, agent)
        elif sub == "load":
            await handle_agents_load(parts, ui, agent)
        else:
            ui.print_message(
                f"Unknown /agents subcommand: [bold red]{sub}[/bold red]\n"
                "Available: [bold cyan]list | add <name> <url> | remove <name> | unload <name> | load[/bold cyan]",
                role="error",
            )

    elif cmd == "/memory":
        # Show agent memory
        memory_file = Path.home() / ".net-deepagent" / ui.agent_name / "agent.md"
        if memory_file.exists():
            ui.console.print(Panel(Markdown(memory_file.read_text()), title="Agent Memory", border_style="blue"))
        else:
            ui.print_message("No memory file found.", role="system")
    
    elif cmd == "/session":
        sub = parts[1].lower() if len(parts) > 1 else "new"
        if sub == "new":
            await handle_new_session(messages, ui)
        elif sub == "delete":
            await handle_delete_session(parts, ui)
        elif sub == "threshold":
            await handle_session_threshold(parts, ui, agent)
        elif sub == "window":
            await handle_session_window(parts, ui, agent)
        elif sub == "resume":
            await handle_resume_session(parts, ui, messages, offset=1)
        else:
            ui.print_message(
                f"Unknown /session subcommand: [bold red]{sub}[/bold red]\n"
                "Available: [bold cyan]new | delete | resume | threshold <value> | window <days>[/bold cyan]",
                role="error",
            )
            
    elif cmd == "/middlewares":
        await handle_middlewares(ui)

    elif cmd == "/exit":
        await handle_exit(messages, ui)
        raise EOFError()

    elif cmd == "/bootup":
        if agent is None:
            ui.print_message("No agent attached to this session.", role="error")
        else:
            await handle_bootup(ui, messages, agent)
    
    else:
        ui.print_message(f"Unknown command: {cmd}", role="error")

async def prompt_and_save_session(messages, ui, prompt_msg: str):
    """Ask use if they want to save session, if so prompt for name and save."""
    if messages:
        ui.console.print(f"[bold yellow]{prompt_msg}[/bold yellow]")
        if await ui.confirm("[bold yellow]Save current session?[/bold yellow]"):
            session_name = (await ui.prompt_simple("[bold blue]Enter session name to save:[/] ")).strip()
            if session_name:
                from net_deepagent_cli.communication.session import save_session # Ensure imports
                from net_deepagent_cli.config import AgentConfig # Already in commands.py
                import json # Already in commands.py
                
                config_manager = AgentConfig(ui.agent_name)
                sessions_dir = config_manager.sessions_dir
                
                # Ensure .json extension
                if not session_name.endswith(".json"):
                    filename = f"{session_name}.json"
                else:
                    filename = session_name
                    
                filepath = sessions_dir / filename
                
                try:
                    # Serialize messages
                    from langchain_core.messages import message_to_dict
                    serialized_messages = [message_to_dict(m) for m in messages]
                    with open(filepath, 'w') as f:
                        json.dump(serialized_messages, f, indent=2)
                    ui.print_message(f"Session saved to [bold cyan]{filename}[/bold cyan]", role="system")
                    # Archive to ChromaDB asynchronously (fire-and-forget, non-blocking)
                    fire_and_forget_archive(messages, session_name)
                    return True
                except Exception as e:
                    ui.print_message(f"Failed to save session: {e}", role="error")
            else:
                ui.print_message("Save cancelled (no name provided).", role="warning")
    return False

async def handle_new_session(messages, ui):
    """Confirm with user to save current session then clear it"""
    await prompt_and_save_session(messages, ui, "You have an active session.")
    messages.clear()
    ui.print_message("✨ [bold green]New session started.[/bold green]", role="system")

async def handle_exit(messages, ui):
    """Handle exit sequence: prompt for save, then skill update, then exit."""
    # 1. Prompt for Session Save
    await prompt_and_save_session(messages, ui, "Session is about to end.")

    # 2. Prompt for Skill Update
    if messages:
        if await ui.confirm("[bold yellow]Do you want to check for skill updates from this session?[/bold yellow]"):
            skill_name = (await ui.prompt_simple("[bold blue]Enter skill name to update (default: network-facts-and-procedures):[/] ")).strip()
            if not skill_name:
                skill_name = "network-facts-and-procedures"
            
            # handle_skill_update(skill_name, source, dry_run, agent_name, ui, messages)
            from net_deepagent_cli.skill_commands import handle_skill_update
            task = await handle_skill_update(skill_name, None, False, ui.agent_name, ui, messages)
            if task:
                await task

    ui.print_message("Exiting...", role="system")

async def handle_delete_session(parts, ui):
    """Delete a saved session file by name"""
    config_manager = AgentConfig(ui.agent_name)
    sessions_dir = config_manager.sessions_dir
    
    session_name = parts[2] if len(parts) > 2 else None
    
    if not session_name:
        # Prompt for name if not provided
        session_name = (await ui.prompt_simple("[bold blue]Enter session name to delete: [/]")).strip()
        if not session_name:
            return

    # Ensure .json extension
    if not session_name.endswith(".json"):
        filename = f"{session_name}.json"
    else:
        filename = session_name
        
    filepath = sessions_dir / filename
    
    if not filepath.exists():
        ui.print_message(f"Session file [bold red]{filename}[/bold red] not found.", role="error")
        return

    # Confirmation
    if await ui.confirm(f"[bold red]Are you sure you want to delete session '{session_name}'?[/bold red]"):
        try:
            filepath.unlink()
            ui.print_message(f"Session [bold cyan]{filename}[/bold cyan] deleted successfully.", role="system")
        except Exception as e:
            ui.print_message(f"Failed to delete session: {e}", role="error")
    else:
        ui.print_message("Deletion cancelled.", role="system")

async def handle_session_threshold(parts: List[str], ui, agent):
    """Adjust the topic drift detection threshold"""
    if not hasattr(agent, 'drift_detector') or agent.drift_detector is None:
        ui.print_message(
            "Topic drift detection is not enabled. Start with [bold]--automatic-context-detection[/bold] to use this command.",
            role="warning"
        )
        return

    new_val = parts[2] if len(parts) > 2 else None
    
    if new_val is None:
        # Just show current value
        current = agent.drift_detector.threshold
        ui.print_message(f"Current drift threshold: [bold cyan]{current}[/bold cyan]", role="system")
        ui.print_message("To change it, use: [bold]/session threshold <0.0-1.0>[/bold]", role="system")
        return

    try:
        threshold = float(new_val)
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        agent.drift_detector.threshold = threshold
        ui.print_message(f"✨ Topic drift threshold updated to: [bold green]{threshold}[/bold green]", role="system")
        
    except ValueError as e:
        ui.print_message(f"Invalid threshold value: [bold red]{new_val}[/bold red]. {str(e)}", role="error")

async def handle_session_window(parts: List[str], ui, agent):
    """Adjust the past interaction lookback window"""
    if not hasattr(agent, 'association_engine') or agent.association_engine is None:
        ui.print_message(
            "Interaction association is not enabled. Start with [bold]--automatic-context-detection[/bold] to use this command.",
            role="warning"
        )
        return

    new_val = parts[2] if len(parts) > 2 else None
    
    if new_val is None:
        current = agent.association_engine.lookback_days
        ui.print_message(f"Current association lookback window: [bold cyan]{current}[/bold cyan] days", role="system")
        ui.print_message("To change it, use: [bold]/session window <days>[/bold]", role="system")
        return

    try:
        days = int(new_val)
        if days < 1:
            raise ValueError("Window must be at least 1 day.")
        
        agent.association_engine.lookback_days = days
        # We might want to rebuild cache if window expanded, but for now simple update
        ui.print_message(f"✨ Association window updated to: [bold green]{days}[/bold green] days", role="system")
        ui.print_message("Note: Large windows may slightly increase scan time on next startup.", role="dim")
        
    except ValueError as e:
        ui.print_message(f"Invalid window value: [bold red]{new_val}[/bold red]. {str(e)}", role="error")

async def handle_resume_session(parts: List[str], ui, messages, offset=0):
    """Resume a saved session file by name or number"""
    config_manager = AgentConfig(ui.agent_name)
    sessions_dir = config_manager.sessions_dir
    
    # offset=0 for /resume <name>
    # offset=1 for /session resume <name>
    name_idx = 1 + offset
    session_name = parts[name_idx] if len(parts) > name_idx else None
    
    if not session_name:
        # List available sessions
        available = list(sessions_dir.glob("*.json"))
        if not available:
            ui.print_message("No saved sessions found.", role="system")
            return
            
        ui.console.print("[bold blue]Available Sessions:[/bold blue]")
        for i, p in enumerate(available):
            ui.console.print(f"  {i+1}. [cyan]{p.stem}[/cyan]")
            
        choice = await ui.prompt_simple("[bold blue]Pick a session number or name (or Enter to cancel):[/] ")
        if not choice:
            return
            
        if choice.isdigit() and 1 <= int(choice) <= len(available):
            filepath = available[int(choice)-1]
        else:
            if not choice.endswith(".json"):
                filepath = sessions_dir / f"{choice}.json"
            else:
                filepath = sessions_dir / choice
    else:
        if not session_name.endswith(".json"):
            filepath = sessions_dir / f"{session_name}.json"
        else:
            filepath = sessions_dir / session_name

    if not filepath.exists():
        ui.print_message(f"Session file [bold red]{filepath.name}[/bold red] not found.", role="error")
        return
        
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            from langchain_core.messages import messages_from_dict
            restored_messages = messages_from_dict(data)
            
        messages.clear()
        messages.extend(restored_messages)
        ui.print_message(f"Resumed session from [bold cyan]{filepath.name}[/bold cyan] ([bold green]{len(messages)}[/bold green] messages restored)", role="system")
        ui.print_message("You can continue the conversation now.", role="system")
    except Exception as e:
        ui.print_message(f"Failed to resume session: {e}", role="error")

async def extract_skills_from_document(doc_path: str, agent_name: str, ui):
    """
    Extract skills from a document and store them in the skills directory.
    This is a stub for future implementation using RAG.
    """
    ui.print_message(f"Initiating skill extraction from: [bold]{doc_path}[/bold]", role="system")
    ui.print_message("Note: Skill extraction logic is currently a placeholder. RAG-based extraction will be implemented in the next phase.", role="system")

async def handle_skills_update(skill_name: str, source: Optional[str], ui, messages):
    """
    Handle checking for updates to a specific skill.
    source can be a document path, or if None, current context is used.
    """
    ui.print_message(f"🔍 Checking for updates to [bold yellow]{skill_name}[/bold yellow]...", role="system")
    
    content = ""
    if source and source.lower() != "context":
        # Load from document
        doc_path = Path(source)
        if not doc_path.exists():
            ui.print_message(f"Source document [bold red]{source}[/bold red] not found.", role="error")
            return
        
        try:
            content = doc_path.read_text()
            ui.print_message(f"Loaded content from [bold cyan]{source}[/bold cyan]", role="system")
        except Exception as e:
            ui.print_message(f"Failed to read source document: {e}", role="error")
            return
    else:
        # Use current context (messages)
        # Aggregate last 15 messages for context
        relevant_messages = messages[-15:] if len(messages) > 15 else messages
        for m in relevant_messages:
            content += f"\n{m.type.upper()}: {m.content}"
        
        ui.print_message("Using current conversation context for update detection.", role="system")

    # Get middleware
    skills_dir = AgentConfig(ui.agent_name).config_dir / "skills"
    middleware = get_skill_learning_middleware(str(skills_dir))
    
    # Trigger detection
    # We use a custom call to the middleware's internal analyzer or just trigger manual update
    # The middleware has _analyze_for_updates but it's internal.
    # However, we can use the detector directly or call analyze. 
    # Actually SkillLearningMiddleware._analyze_for_updates is what we want.
    middleware._analyze_for_updates(content)
    
    # Check if anything was added for this skill
    pending = middleware.get_pending_updates(skill_name)
    if not pending or not pending.get(skill_name):
        ui.print_message(f"No new information found for [bold yellow]{skill_name}[/bold yellow].", role="system")
        return
        
    # Trigger the UI for review (only for this skill)
    await handle_skill_updates(middleware, ui, skill_name=skill_name)

async def handle_middlewares(ui):
    """Interactive menu to toggle and configure custom middlewares"""
    from net_deepagent_cli.middleware_manager import MiddlewareManager
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    
    manager = MiddlewareManager(ui.agent_name)
    
    while True:
        all_middlewares = manager.list_all()
        if not all_middlewares:
            ui.print_message("No custom middlewares registered.", role="warning")
            return

        choices = []
        for key, config in all_middlewares.items():
            status = "[ON]" if config["enabled"] else "[OFF]"
            choices.append(Choice(
                value=key,
                name=f"{status} {config['name']} - {config['description']}"
            ))
        choices.append(Choice(value="done", name="Done"))

        choice = await inquirer.select(
            message="Configure Custom Middlewares:",
            choices=choices,
            default="done",
            qmark="⚙",
        ).execute_async()

        if choice == "done":
            break
        
        # Sub-menu for the selected middleware
        mw_cfg = all_middlewares[choice]
        status_text = "[ON]" if mw_cfg["enabled"] else "[OFF]"
        
        sub_choices = [
            Choice(value="toggle", name=f"{status_text} Toggle State"),
            Choice(value="config", name="⚙ Configure Parameters"),
            Choice(value="back", name="Back")
        ]
        
        sub_choice = await inquirer.select(
            message=f"Options for {mw_cfg['name']}:",
            choices=sub_choices,
            default="back"
        ).execute_async()
        
        if sub_choice == "toggle":
            new_state = not mw_cfg["enabled"]
            manager.toggle_middleware(choice, new_state)
            ui.print_message(f"Middleware '{mw_cfg['name']}' {'enabled' if new_state else 'disabled'}.", role="system")
        elif sub_choice == "config":
            if choice == "netpii":
                await configure_netpii_params(ui, manager)
            elif choice == "advanced_context":
                await configure_context_params(ui, manager)
            else:
                ui.print_message(f"No additional configuration available for {mw_cfg['name']}.", role="dim")

async def configure_netpii_params(ui, manager):
    """Sub-menu for NetPII PII types selection."""
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from custom_middleware.netpii_middlewares import PII_DETECTORS
    
    ui.console.print("\n[bold cyan]--- NetPII Configuration ---[/bold cyan]")
    
    all_mw = manager.list_all()
    current_params = all_mw.get("netpii", {}).get("params", {})
    current_types = current_params.get("pii_types", "all")
    
    if current_types == "all":
        current_types = list(PII_DETECTORS.keys())
    elif isinstance(current_types, str):
        current_types = [current_types]
    
    # Create Choice objects with enabled status for existing types
    choices = [
        Choice(value=t, name=f"{t} (Detector)", enabled=(t in current_types)) 
        for t in PII_DETECTORS.keys()
    ]
        
    selected_types = await inquirer.checkbox(
        message="Select PII types to mask:",
        choices=choices,
        instruction="(Space to toggle, Enter to confirm)",
        transformer=lambda result: f"{len(result)} types selected"
    ).execute_async()
    
    if selected_types is not None:
        if not selected_types:
            ui.print_message("No types selected. NetPII will be effectively disabled for input masking.", role="warning")
            manager.update_middleware_params("netpii", {"pii_types": []})
        else:
            manager.update_middleware_params("netpii", {"pii_types": selected_types})
            ui.print_message(f"Successfully updated PII types: [bold green]{', '.join(selected_types)}[/bold green]", role="system")
    else:
        ui.print_message("Configuration cancelled.", role="system")

async def configure_context_params(ui, manager):
    """Interactive editor for Advanced Context parameters."""
    from InquirerPy import inquirer
    
    all_mw = manager.list_all()
    params = all_mw.get("advanced_context", {}).get("params", {}).copy()
    
    # We edit key parameters one by one for simplicity in this version
    new_ratio = await inquirer.text(
        message="Enter trigger ratio (0.1 to 0.9):",
        default=str(params.get("trigger_ratio", 0.85)),
        validate=lambda x: 0 < float(x) < 1.0 if x.replace('.', '', 1).isdigit() else False
    ).execute_async()
    
    params["trigger_ratio"] = float(new_ratio)
    
    new_skills = await inquirer.text(
        message="Number of skills to keep:",
        default=str(params.get("keep_skills", 1)),
        validate=lambda x: x.isdigit()
    ).execute_async()
    params["keep_skills"] = int(new_skills)

    manager.update_middleware_params("advanced_context", params)
    ui.print_message("Advanced Context parameters updated.", role="system")


# ---------------------------------------------------------------------------
# /bootup command
# ---------------------------------------------------------------------------

BOOTUP_PROMPT = (
    "You are now online and fully operational. "
    "Please do the following:\n"
    "1. Confirm that you are awake and ready to receive tasks.\n"
    "2. Briefly introduce your capabilities as they apply to the current environment.\n"
    "3. Report any ready processes or relevant operational facts you are aware of "
    "(e.g. connected MCP servers, available tools, active subagents, monitored systems).\n"
    "4. Check whether any routine or automatable tasks can be started right now "
    "and, if so, propose them with a brief rationale.\n"
    "5. Suggest a sensible starting point or set of next steps for the operator."
    "6. if any recurrent task are in the fact-and-procedures u can initiate them."
)


async def handle_bootup(ui, messages, agent):
    """Send a wake-up / readiness prompt to the LLM and stream the response."""
    from langchain_core.messages import HumanMessage
    from net_deepagent_cli.loop import stream_agent_response

    ui.print_message(
        "\U0001f680 Sending bootup signal to agent \u2014 please wait...",
        role="system"
    )
    messages.append(HumanMessage(content=BOOTUP_PROMPT))
    await stream_agent_response(agent, messages, ui, auto_approve=True)
