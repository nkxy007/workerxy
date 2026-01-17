from rich.markdown import Markdown
from pathlib import Path
from net_deepagent_cli.agent import SkillsMiddleware

async def handle_command(command: str, ui, messages):
    """Handle special slash commands"""
    parts = command.split()
    cmd = parts[0].lower()
    
    if cmd == "/help":
        ui.console.print("""
[bold]Available Commands:[/bold]
  [bold cyan]/clear[/bold cyan]      - Clear conversation history
  [bold cyan]/tokens[/bold cyan]     - Show token usage for the entire session
  [bold cyan]/context[/bold cyan]    - Analyze current context (messages and system prompt)
  [bold cyan]/skills[/bold cyan]            - List available skills
  [bold cyan]/skills add <path>[/bold cyan]    - Extract and add skills from a document
  [bold cyan]/memory[/bold cyan]     - Show current agent memory
  [bold cyan]/exit[/bold cyan]       - Exit the CLI
  [bold cyan]/help[/bold cyan]       - Show this help message
        """)
    
    elif cmd == "/clear":
        messages.clear()
        ui.print_message("Conversation cleared", role="system")
    
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
        if len(parts) > 2 and parts[1].lower() in ["add", "extract"]:
            doc_path = parts[2]
            await extract_skills_from_document(doc_path, ui.agent_name, ui)
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
    
    elif cmd == "/memory":
        # Show agent memory
        memory_file = Path.home() / ".net-deepagent" / ui.agent_name / "agent.md"
        if memory_file.exists():
            ui.console.print(Panel(Markdown(memory_file.read_text()), title="Agent Memory", border_style="blue"))
        else:
            ui.print_message("No memory file found.", role="system")
    
    elif cmd == "/exit":
        ui.print_message("Exiting...", role="system")
        raise EOFError()
    
    else:
        ui.print_message(f"Unknown command: {cmd}", role="error")

async def extract_skills_from_document(doc_path: str, agent_name: str, ui):
    """
    Extract skills from a document and store them in the skills directory.
    This is a stub for future implementation using RAG.
    """
    ui.print_message(f"Initiating skill extraction from: [bold]{doc_path}[/bold]", role="system")
    
    # Placeholder for future implementation:
    # 1. Load document (doc_path)
    # 2. Use RAG/LLM to identify best practices or specialized knowledge
    # 3. Create a folder in ~/.net-deepagent/<agent_name>/skills/<skill_name>
    # 4. Write SKILL.md with frontmatter and instructions
    
    ui.print_message("Note: Skill extraction logic is currently a placeholder. RAG-based extraction will be implemented in the next phase.", role="system")

from rich.panel import Panel
