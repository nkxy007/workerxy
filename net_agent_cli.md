# Net DeepAgent CLI Implementation Plan

Based on analysis of the LangChain deepagents-cli implementation, here's a comprehensive plan for building a similar terminal UI for your `net_deepagent`.

## Architecture Overview

The deepagents-cli follows this architecture:
```
CLI Entry Point (main)
    ↓
Agent Creation (create_cli_agent)
    ↓
Middleware Stack (Memory + Skills)
    ↓
Core Deep Agent (your net_deepagent)
    ↓
Rich Terminal UI (Streaming + HITL)
```

## Key Components to Implement

### 1. **CLI Entry Point (`net_deepagent_cli/cli.py`)**

```python
import asyncio
import argparse
from pathlib import Path
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Net DeepAgent CLI")
    parser.add_argument("--agent", default="agent", help="Agent name")
    parser.add_argument("--model", default="gpt-5-mini", help="Main model")
    parser.add_argument("--subagent-model", default="gpt-5-mini-minimal", help="Subagent model")
    parser.add_argument("--design-model", default="gpt-5.1", help="Design model")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve tool usage")
    parser.add_argument("--mcp-server", default="http://localhost:8000/mcp", help="MCP server URL")
    
    args = parser.parse_args()
    
    # Run async main
    asyncio.run(run_agent(args))

async def run_agent(args):
    """Run the agent with CLI interface"""
    console = Console()
    
    # Display startup banner
    console.print("[bold blue]Net DeepAgent CLI[/bold blue]")
    console.print(f"Agent: {args.agent}")
    console.print(f"Model: {args.model}")
    
    # Create agent
    from net_deepagent_cli.agent import create_cli_agent
    agent = await create_cli_agent(
        agent_name=args.agent,
        mcp_server_url=args.mcp_server,
        main_model_name=args.model,
        subagent_model_name=args.subagent_model,
        design_model_name=args.design_model,
        auto_approve=args.auto_approve
    )
    
    # Start interactive loop
    await interactive_loop(agent, args, console)
```

### 2. **Agent Creation with Middleware (`net_deepagent_cli/agent.py`)**

```python
from typing import Optional
from pathlib import Path
from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware, SubAgentMiddleware

class AgentMemoryMiddleware:
    """Load and inject agent memory from ~/.net-deepagent/<agent_name>/agent.md"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.memory_dir = Path.home() / ".net-deepagent" / agent_name
        self.memory_file = self.memory_dir / "agent.md"
        
    async def __call__(self, state, config):
        # Load memory if exists
        if self.memory_file.exists():
            memory_content = self.memory_file.read_text()
            # Inject into system prompt
            state["system_prompt"] = f"{state.get('system_prompt', '')}\n\n## Agent Memory\n{memory_content}"
        return state

class SkillsMiddleware:
    """Progressive disclosure skills system"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.skills_dir = Path.home() / ".net-deepagent" / agent_name / "skills"
        self.project_skills_dir = Path.cwd() / ".net-deepagent" / "skills"
        
    def scan_skills(self):
        """Scan for available skills and extract metadata"""
        skills = []
        
        for skills_dir in [self.skills_dir, self.project_skills_dir]:
            if not skills_dir.exists():
                continue
                
            for skill_path in skills_dir.glob("*/SKILL.md"):
                metadata = self.parse_skill_metadata(skill_path)
                skills.append({
                    "name": metadata.get("name", skill_path.parent.name),
                    "description": metadata.get("description", ""),
                    "path": skill_path
                })
        
        return skills
    
    def parse_skill_metadata(self, skill_path: Path):
        """Parse YAML frontmatter from SKILL.md"""
        import yaml
        content = skill_path.read_text()
        
        # Extract YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1])
        return {}
    
    async def __call__(self, state, config):
        """Inject skill list into system prompt"""
        skills = self.scan_skills()
        
        if skills:
            skills_text = "## Available Skills\n\n"
            for skill in skills:
                skills_text += f"- **{skill['name']}**: {skill['description']}\n"
            skills_text += "\nTo use a skill, read its full instructions with read_file('{path}')\n"
            
            state["system_prompt"] = f"{state.get('system_prompt', '')}\n\n{skills_text}"
        
        return state

async def create_cli_agent(
    agent_name: str,
    mcp_server_url: str,
    main_model_name: str,
    subagent_model_name: str,
    design_model_name: str,
    auto_approve: bool = False
):
    """Create agent with CLI-specific middleware"""
    
    # Create base agent using your existing function
    from your_module import create_network_agent
    base_agent = await create_network_agent(
        mcp_server_url=mcp_server_url,
        main_model_name=main_model_name,
        subagent_model_name=subagent_model_name,
        design_model_name=design_model_name
    )
    
    # Add CLI-specific middleware
    # Note: This is pseudocode - actual implementation depends on your agent's structure
    memory_middleware = AgentMemoryMiddleware(agent_name)
    skills_middleware = SkillsMiddleware(agent_name)
    
    # Wrap agent with middleware
    # The exact method depends on how your agent is structured
    wrapped_agent = apply_middleware(base_agent, [
        memory_middleware,
        skills_middleware
    ])
    
    return wrapped_agent
```

### 3. **Rich Terminal UI (`net_deepagent_cli/ui.py`)**

```python
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from pathlib import Path
import difflib

class TerminalUI:
    """Rich terminal interface for agent interaction"""
    
    def __init__(self, agent_name: str):
        self.console = Console()
        self.agent_name = agent_name
        self.history_file = Path.home() / ".net-deepagent" / agent_name / "history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.session = PromptSession(
            history=FileHistory(str(self.history_file))
        )
        
        # Token tracking
        self.total_tokens = 0
        
    def print_banner(self):
        """Display startup banner"""
        banner = Panel.fit(
            "[bold blue]Net DeepAgent CLI[/bold blue]\n"
            f"Agent: {self.agent_name}\n"
            "Type /help for commands",
            border_style="blue"
        )
        self.console.print(banner)
    
    async def get_user_input(self):
        """Get user input with history"""
        try:
            user_input = await self.session.prompt_async(
                "> ",
                multiline=False
            )
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            return None
    
    def print_message(self, message: str, role: str = "assistant"):
        """Print a message with formatting"""
        if role == "assistant":
            # Render markdown for assistant messages
            self.console.print(Markdown(message))
        else:
            self.console.print(f"[bold green]User:[/bold green] {message}")
    
    def print_tool_call(self, tool_name: str, args: dict):
        """Display tool call"""
        self.console.print(
            f"[bold yellow]⚙ {tool_name}[/bold yellow]({', '.join(f'{k}={v}' for k, v in args.items())})"
        )
    
    def show_file_diff(self, old_content: str, new_content: str, filename: str):
        """Show file modification diff"""
        diff = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}"
        ))
        
        if diff:
            diff_text = "".join(diff)
            syntax = Syntax(diff_text, "diff", theme="monokai")
            self.console.print(Panel(syntax, title=f"Diff: {filename}"))
    
    def request_approval(self, action: str, details: str) -> str:
        """Request human approval for action"""
        panel = Panel(
            f"[bold]Action:[/bold] {action}\n\n{details}\n\n"
            "[1] Approve  [2] Edit  [3] Reject",
            title="Approval Required",
            border_style="yellow"
        )
        self.console.print(panel)
        
        choice = self.console.input("Choice [1-3]: ").strip()
        
        if choice == "1":
            return "approve"
        elif choice == "2":
            return "edit"
        else:
            return "reject"
    
    def show_progress(self, message: str):
        """Show progress indicator"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )
    
    def update_token_count(self, tokens: int):
        """Update and display token count"""
        self.total_tokens += tokens
        self.console.print(
            f"[dim]Tokens: {tokens:,} (Total: {self.total_tokens:,})[/dim]"
        )
```

### 4. **Interactive Loop with Streaming (`net_deepagent_cli/loop.py`)**

```python
import asyncio
from typing import AsyncIterator

async def interactive_loop(agent, args, console):
    """Main interactive loop with streaming"""
    from net_deepagent_cli.ui import TerminalUI
    
    ui = TerminalUI(args.agent)
    ui.print_banner()
    
    # Session state
    messages = []
    
    while True:
        # Get user input
        user_input = await ui.get_user_input()
        
        if user_input is None:
            # Ctrl+C or EOF
            console.print("[yellow]Goodbye![/yellow]")
            break
        
        # Handle special commands
        if user_input.startswith("/"):
            await handle_command(user_input, ui, messages)
            continue
        
        if not user_input:
            continue
        
        # Add user message
        messages.append({"role": "user", "content": user_input})
        
        # Stream agent response
        await stream_agent_response(agent, messages, ui, args.auto_approve)

async def stream_agent_response(agent, messages, ui, auto_approve):
    """Stream agent response with real-time updates"""
    
    current_message = ""
    
    try:
        # Stream from agent
        async for chunk in agent.astream(
            {"messages": messages},
            stream_mode="messages"  # or "values" depending on your agent
        ):
            # Handle different chunk types
            if "messages" in chunk:
                new_messages = chunk["messages"]
                
                for msg in new_messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        # Tool call
                        for tool_call in msg.tool_calls:
                            ui.print_tool_call(
                                tool_call["name"],
                                tool_call["args"]
                            )
                            
                            # Request approval if needed
                            if not auto_approve and requires_approval(tool_call["name"]):
                                approval = ui.request_approval(
                                    tool_call["name"],
                                    str(tool_call["args"])
                                )
                                
                                if approval == "reject":
                                    # Handle rejection
                                    pass
                    
                    elif hasattr(msg, "content") and msg.content:
                        # Text content
                        current_message += msg.content
                        # For streaming, you might want to print incrementally
                        ui.print_message(msg.content, role="assistant")
        
        # Add final message to history
        if current_message:
            messages.append({"role": "assistant", "content": current_message})
    
    except Exception as e:
        ui.console.print(f"[bold red]Error:[/bold red] {str(e)}")

def requires_approval(tool_name: str) -> bool:
    """Check if tool requires human approval"""
    sensitive_tools = ["execute", "write_file", "delete_file", "http_request"]
    return tool_name in sensitive_tools

async def handle_command(command: str, ui, messages):
    """Handle special slash commands"""
    parts = command.split()
    cmd = parts[0].lower()
    
    if cmd == "/help":
        ui.console.print("""
[bold]Available Commands:[/bold]
  /clear      - Clear conversation history
  /tokens     - Show token usage
  /save       - Save conversation
  /load       - Load conversation
  /skills     - List available skills
  /memory     - Show agent memory
  /exit       - Exit the CLI
        """)
    
    elif cmd == "/clear":
        messages.clear()
        ui.console.print("[green]Conversation cleared[/green]")
    
    elif cmd == "/tokens":
        ui.console.print(f"[bold]Total tokens:[/bold] {ui.total_tokens:,}")
    
    elif cmd == "/skills":
        # List available skills
        from net_deepagent_cli.agent import SkillsMiddleware
        skills_mw = SkillsMiddleware(ui.agent_name)
        skills = skills_mw.scan_skills()
        
        ui.console.print("[bold]Available Skills:[/bold]")
        for skill in skills:
            ui.console.print(f"  • {skill['name']}: {skill['description']}")
    
    elif cmd == "/memory":
        # Show agent memory
        from pathlib import Path
        memory_file = Path.home() / ".net-deepagent" / ui.agent_name / "agent.md"
        if memory_file.exists():
            ui.console.print(Markdown(memory_file.read_text()))
        else:
            ui.console.print("[yellow]No memory file found[/yellow]")
    
    elif cmd == "/exit":
        raise EOFError()
```

### 5. **Configuration Management (`net_deepagent_cli/config.py`)**

```python
from pathlib import Path
from typing import Optional
import yaml

class AgentConfig:
    """Manage agent configuration"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.config_file = self.config_dir / "config.yaml"
        
        # Create directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / "skills").mkdir(exist_ok=True)
        (self.config_dir / "memories").mkdir(exist_ok=True)
    
    def load_config(self) -> dict:
        """Load agent configuration"""
        if self.config_file.exists():
            return yaml.safe_load(self.config_file.read_text())
        return self.default_config()
    
    def save_config(self, config: dict):
        """Save agent configuration"""
        self.config_file.write_text(yaml.dump(config))
    
    def default_config(self) -> dict:
        """Default configuration"""
        return {
            "agent_name": self.agent_name,
            "main_model": "gpt-5-mini",
            "subagent_model": "gpt-5-mini-minimal",
            "design_model": "gpt-5.1",
            "mcp_server": "http://localhost:8000/mcp",
            "auto_approve": False
        }

def find_project_root() -> Optional[Path]:
    """Find project root by looking for .git or .net-deepagent"""
    current = Path.cwd()
    
    while current != current.parent:
        if (current / ".git").exists() or (current / ".net-deepagent").exists():
            return current
        current = current.parent
    
    return None
```

### 6. **Package Structure**

```
net-deepagent-cli/
├── pyproject.toml
├── README.md
├── net_deepagent_cli/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── cli.py               # Main CLI logic
│   ├── agent.py             # Agent creation with middleware
│   ├── ui.py                # Rich terminal UI
│   ├── loop.py              # Interactive loop
│   ├── config.py            # Configuration management
│   └── commands.py          # Slash commands
└── tests/
    └── test_cli.py
```

### 7. **Dependencies (`pyproject.toml`)**

```toml
[project]
name = "net-deepagent-cli"
version = "0.1.0"
description = "CLI interface for Net DeepAgent"
dependencies = [
    "rich>=13.0.0",
    "prompt-toolkit>=3.0.0",
    "pyyaml>=6.0",
    "your-net-deepagent-package"
]

[project.scripts]
net-deepagent = "net_deepagent_cli.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Key Features to Implement

### Phase 1: Basic CLI (MVP)
1. ✅ Command-line argument parsing
2. ✅ Agent initialization
3. ✅ Basic prompt loop
4. ✅ Message streaming
5. ✅ Simple output formatting

### Phase 2: Rich UI
1. ✅ Markdown rendering
2. ✅ Syntax highlighting
3. ✅ Progress indicators
4. ✅ Token tracking
5. ✅ File diff display

### Phase 3: Human-in-the-Loop
1. ✅ Tool approval prompts
2. ✅ Edit/reject options
3. ✅ Auto-approve mode
4. ✅ Sensitive tool detection

### Phase 4: Memory & Skills
1. ✅ Agent memory system (~/.net-deepagent/<agent_name>/agent.md)
2. ✅ Skills directory structure
3. ✅ YAML frontmatter parsing
4. ✅ Progressive disclosure
5. ✅ Project-aware configuration

### Phase 5: Advanced Features
1. ⬜ Sandbox integration (optional)
2. ⬜ LangSmith tracing
3. ⬜ Session management
4. ⬜ Conversation export
5. ⬜ Multiple agent support

## Integration with Your Net DeepAgent

Your `create_network_agent` function already returns a configured agent. The CLI wrapper should:

1. **Call your existing function** to create the base agent
2. **Add CLI-specific middleware** for memory and skills
3. **Wrap streaming** to display in terminal with Rich
4. **Add HITL logic** to pause for approvals

Example integration:

```python
# In your agent.py
from your_module import create_network_agent as create_base_agent

async def create_cli_agent(agent_name, **kwargs):
    # Create base agent (your existing function)
    base_agent = await create_base_agent(**kwargs)
    
    # Add CLI middleware (memory, skills, UI)
    cli_agent = wrap_with_cli_middleware(
        base_agent,
        agent_name=agent_name
    )
    
    return cli_agent
```

## Testing Strategy

1. **Unit tests** for middleware (memory loading, skill scanning)
2. **Integration tests** for agent creation
3. **Manual testing** for UI/UX
4. **E2E tests** for complete workflows

## Next Steps

1. **Set up project structure** as shown above
2. **Implement Phase 1** (basic CLI) first
3. **Test with your existing agent** to ensure compatibility
4. **Gradually add features** from Phases 2-5
5. **Iterate based on usage** and feedback

## Differences from DeepAgents CLI

Your implementation can be simpler since you're not building a general-purpose framework:

- **Simpler middleware** (just memory + skills, no need for complex chaining)
- **Custom for your agent** (no need to support arbitrary backends)
- **Focus on MCP integration** (your key differentiator)
- **Network-specific features** (leverage your subagents design)

## Resources

- **DeepAgents docs**: https://docs.langchain.com/oss/python/deepagents/cli
- **Rich library**: https://rich.readthedocs.io/
- **Prompt Toolkit**: https://python-prompt-toolkit.readthedocs.io/
- **LangGraph**: For understanding streaming and state management
