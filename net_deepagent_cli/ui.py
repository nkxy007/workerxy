from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter, Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from pathlib import Path
import difflib
from typing import Optional, Iterable, Any

class HierarchicalCompleter(Completer):
    """
    Completer that suggests top-level /commands first, 
    and then suggests subcommands for specific base commands.
    """
    def __init__(self, structure: dict):
        self.structure = structure
        self.top_level_completer = WordCompleter(
            list(self.structure.keys()),
            meta_dict={k: v.get("desc", "") for k, v in self.structure.items()},
            ignore_case=True,
            match_middle=True
        )

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()
        parts = text.split()
        
        # If no words yet or currently typing the first word (no space after it)
        if len(parts) == 0 or (len(parts) == 1 and not text.endswith(" ")):
            yield from self.top_level_completer.get_completions(document, complete_event)
            return

        # If we have a first word and it's a known command with subcommands
        base_cmd = parts[0].lower()
        if base_cmd in self.structure:
            subs = self.structure[base_cmd].get("subs", {})
            if subs:
                # Suggest subcommands if we are typing the second word
                if len(parts) == 1 and text.endswith(" "):
                    # Just started typing second word
                    sub_completer = WordCompleter(
                        list(subs.keys()),
                        meta_dict=subs,
                        ignore_case=True,
                        match_middle=True
                    )
                    yield from sub_completer.get_completions(document, complete_event)
                elif len(parts) == 2 and not text.endswith(" "):
                    # In the middle of typing second word
                    sub_completer = WordCompleter(
                        list(subs.keys()),
                        meta_dict=subs,
                        ignore_case=True,
                        match_middle=True
                    )
                    yield from sub_completer.get_completions(document, complete_event)

class TerminalUI:
    """Rich terminal interface for agent interaction"""
    
    # Define a shared command structure for help and completion
    COMMAND_STRUCTURE = {
        "/help": {"desc": "Show available commands"},
        "/clear": {"desc": "Clear conversation history"},
        "/save": {"desc": "Save current context to session"},
        "/resume": {"desc": "Resume a saved session"},
        "/sessions": {"desc": "List all saved sessions"},
        "/tokens": {"desc": "Show token usage"},
        "/context": {"desc": "Analyze current context"},
        "/skills": {
            "desc": "Manage and list skills",
            "subs": {
                "list": "List available skills",
                "add": "Create a new skill from a document: /skills add <doc> [skill_name]",
                "extract": "Alias for add",
                "update": "Update skill from context or doc: /skills update [skill_name] [source] [--dry-run]"
            }
        },
        "/agents": {
            "desc": "Manage A2A agents",
            "subs": {
                "list":   "List all registered agents and their session status",
                "add":    "Persist + load an agent: /agents add <name> <url>",
                "remove": "Remove from registry and unload: /agents remove <name>",
                "unload": "Unload from session only: /agents unload <name>",
                "load":   "Reload all registry agents into session",
            }
        },
        "/automata": {
            "desc": "Manage background tasks",
            "subs": {
                "list": "List all scheduled tasks",
                "add": "Add a new background task",
                "remove": "Remove a task by ID",
                "stop": "Stop a task by ID",
                "resume": "Resume a stale task",
                "logs": "List execution logs for a task",
                "view": "View a specific log file",
                "help": "Show automata commands"
            }
        },
        "/memory": {"desc": "Show current agent memory"},
        "/session": {
            "desc": "Session management shortcuts",
            "subs": {
                "new": "Start a new session (prompts to save current first)",
                "delete": "Delete a saved session by name: /session delete <name>",
                "resume": "Resume a saved session by name: /session resume <name>",
                "threshold": "Adjust topic drift sensitivity (0.0-1.0): /session threshold <value>",
                "window": "Adjust lookback window in days: /session window <days>",
            }
        },
        "/middlewares": {"desc": "Manage and toggle custom middlewares"},
        "/exit": {"desc": "Exit the CLI"}
    }
    
    def __init__(self, agent_name: str, logger: Optional[Any] = None):
        self.console = Console(force_terminal=True, force_interactive=False)
        self.agent_name = agent_name
        self.logger = logger
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.history_file = self.config_dir / "history"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = PromptSession(
            history=FileHistory(str(self.history_file))
        )
        # Secondary session for simple prompts to avoid history/completion leak
        self._simple_session = PromptSession()
        
        # Define commands with descriptions for autocompletion
        self.command_meta = {k: v["desc"] for k, v in self.COMMAND_STRUCTURE.items()}
        self.completer = HierarchicalCompleter(self.COMMAND_STRUCTURE)
        
        # Token tracking
        self.total_tokens = 0
        
    def print_banner(self):
        """Display startup banner with CoworkerX Networking word art"""

        art = r"""

        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@**++++++%@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+++**+@+++++*@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@=##################*@@@@@@@@@@@@@@@@@@@@@@@@@+++@@@@++@@@@+++#@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@-                   *@@@@@@@@@@@@@@@@@@@@@@@*+*@@@@@++*@@@@@++*@@@@
@@@@@@===@@@@@@@@@@@@@@@@@@@:              :    *@@@@@@@@@@@@@@@@@@@@@@*+@@@@@@+++++@@@@@+++@@@
@@@@@+====@@@@@@@@@@@@@@@@@@:              ##   *@@@@@@@@@@@@@@@@@@@@@++@@@@@@+*++*+*@@@@@*+*@@
@@@@*+++==@@@@@@@@@@@@@@@@@@:          #######- *@@@@@@@@@@@@@@@@@@@@*+@@@@@@@@@*+@*@@@@@@@++@@
@@@***+++****@@@@@@@@@@@@@@@:          #######. *@@@@@@@@@@@@@@@@@@@@++@@@@@@@@@++@@@@@@@@@@**@
@@*****+@*#@*@@@@@@@@@@@@@@@:     :        #*   *@@@@@@@@@@@@@@@@@@@++@@@@@@@@@@*+@@@@@@@@@@=+@
@==****@@*@@*#@@@@@@@@@@@@@@:    ##        .    *@@@@@@@@@@@@@@@@@@@++@@@@@@@@@@*+@@@@@@@@@@@+*
====+*@@@***@@@@@@@@@@@@@@@@:  -#######         *@@@@@@@@@@@@@@@@@@@+@@@@@@@@@@@*+@@@+@@@@@@@++
======@@@@**@@@@@@@@@@@@@@@@:   -##====         *@@@@@@@@@@@@@@@@@@++@@@@@@@++*@++@@*+@@@@@@@@+
=======@@@@@@@@@@@@@@@@@@@@@:     #      #      *@@@@@@@@@@@@@@@@@@*+@@@@@@@@*++++@++@@@@@@@@@+
@======+@@@@@@@@@@@@@@@@@@@@:            ##=    *@@@@@@@@@@@@@@@@@@+*+++++++++++++*++++++++++@+
@@+++++++#@@@@@@@@@@@@@@@@@@:        ########   *@@@@@@@@@@@@@@@@@@++@@@@@@@@*+*++@++@@@@@@@@@+
@@@+++****@@@@@@@@@@@@@@@@@@:        ....##+    *@@@@@@@@@@@@@@@@@@++@@@@@@@+++@++@@+*@@@@@@@@+
@@@@@*****#@@@@@@@@@@@@@@@@@:   #        #      *@@@@@@@@@@@@@@@@@@@+@@@@@@@@*@@++@@@+@@@@@@@*+
@@@@@*****#@@@@@@@@@@@@@@@@@: =##----           *@@@@@@@@@@@@@@@@@@@++@@@@@@@@@@*+@@@@@@@@@@@*+
@@@==========@@@@@@@@@@@@@@@:-#######           *@@@@@@@@@@@@@@@@@@@**@@@@@@@@@@*+@@@@@@@@@@@+@
@@===========@@@@@@@@@@@@@@@:  ##               *@@@@@@@@@@@@@@@@@@@@+*@@@@@@@@@*+@@@@@@@@@@**@
@@+++++++++++%@@@@@@@@@@@@@@:   :               *@@@@@@@@@@@@@@@@@@@@*+@@@@@@@@@*+@@@@@@@@@++#@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@:                   *@@@@@@@@@@@@@@@@@@@@@++@@@@@@**++@*@@@@@@@++@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@*###################@@@@@@@@@@@@@@@@@@@@@@@+*@@@@@++++++@@@@@@++@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+*@@@@@*++*@@@@@+++@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@++*@@@@+*@@@@**+*@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+++*+@@@@@*++*@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*++++++++*@@@@@@@@@

        
 ██╗    ██╗  ██████╗  ██████╗  ██╗  ██╗ ███████╗ ██████╗  ██╗  ██╗ ██╗   ██╗
 ██║    ██║ ██╔═══██╗ ██╔══██╗ ██║ ██╔╝ ██╔════╝ ██╔══██╗ ╚██╗██╔╝ ╚██╗ ██╔╝
 ██║ █╗ ██║ ██║   ██║ ██████╔╝ █████╔╝  █████╗   ██████╔╝  ╚███╔╝   ╚████╔╝ 
 ██║███╗██║ ██║   ██║ ██╔══██╗ ██╔═██╗  ██╔══╝   ██╔══██╗  ██╔██╗    ╚██╔╝  
 ╚███╔███╔╝ ╚██████╔╝ ██║  ██║ ██║  ██╗ ███████╗ ██║  ██║ ██╔╝ ██╗    ██║   
  ╚══╝╚══╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝    ╚═╝   

 ███╗   ██╗ ███████╗ ████████╗ ██╗    ██╗  ██████╗  ██████╗  ██╗  ██╗ ██╗ ███╗   ██╗  ██████╗ 
 ████╗  ██║ ██╔════╝ ╚══██╔══╝ ██║    ██║ ██╔═══██╗ ██╔══██╗ ██║ ██╔╝ ██║ ████╗  ██║ ██╔════╝ 
 ██╔██╗ ██║ █████╗      ██║    ██║ █╗ ██║ ██║   ██║ ██████╔╝ █████╔╝  ██║ ██╔██╗ ██║ ██║  ███╗
 ██║╚██╗██║ ██╔══╝      ██║    ██║███╗██║ ██║   ██║ ██╔══██╗ ██╔═██╗  ██║ ██║╚██╗██║ ██║   ██║
 ██║ ╚████║ ███████╗    ██║    ╚███╔███╔╝ ╚██████╔╝ ██║  ██║ ██║  ██╗ ██║ ██║ ╚████║ ╚██████╔╝
 ╚═╝  ╚═══╝ ╚══════╝    ╚═╝     ╚══╝╚══╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝ ╚═╝  ╚═══╝  ╚═════╝ 
        """
        self.console.print(f"[bold cyan]{art}[/bold cyan]")
        banner = Panel.fit(
            f"Agent: [bold yellow]{self.agent_name}[/bold yellow] | "
            "Type [bold cyan]/help[/bold cyan] for commands",
            border_style="blue",
            title="[bold blue]workerXY Networking CLI[/bold blue]"
        )
        self.console.print(banner)
        self.console.print("")
        import sys
        sys.stdout.flush()
    
    async def get_user_input(self) -> Optional[str]:
        """Get user input with history"""
        try:
            user_input = await self.session.prompt_async(
                "> ",
                multiline=False,
                completer=self.completer
            )
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            return None

    async def prompt_simple(self, prompt_text: str, default: str = "") -> str:
        """
        Robust async prompt for simple text input using prompt_toolkit.
        Handles special keys correctly and avoids event loop conflicts.
        Isolates from main completion/history.
        """
        try:
            return await self._simple_session.prompt_async(prompt_text, default=default)
        except (KeyboardInterrupt, EOFError):
            return ""

    async def confirm(self, prompt_text: str) -> bool:
        """
        Robust async helper for y/n questions.
        """
        ans = (await self.prompt_simple(f"{prompt_text} (y/n): ")).lower()
        return ans in ['y', 'yes']
    
    async def prompt_new_session_drift(self) -> bool:
        """
        Displays a notice that drift was detected and asks if user wants a new session.
        """
        self.console.print("\n[bold yellow]⚡ This question seems off-topic compared to the current session history.[/bold yellow]")
        return await self.confirm("[bold cyan]Would you like to start a new session?[/bold cyan]")

    async def prompt_resume_session(self, session_name: str, time_hint: str) -> bool:
        """
        Asks if the user wants to resume a found past session.
        """
        self.console.print(f"\n[bold green]💡 I found a related discussion from {time_hint}: \"{session_name}\"[/bold green]")
        return await self.confirm("[bold cyan]Would you like to resume this session?[/bold cyan]")

    def normalize_content(self, message: Any) -> str:
        """
        Normalizes message content (string or list of blocks) to a single string.
        Useful for models using response API or Anthropic content blocks.
        """
        if isinstance(message, str):
            return message
        elif isinstance(message, list):
            text_content = ""
            for block in message:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content += block.get("text", "")
                elif isinstance(block, str):
                    text_content += block
            return text_content
        else:
            return str(message)

    def print_message(self, message: Any, role: str = "assistant"):
        """Print a message with formatting. Handles both string and complex content blocks."""
        text_content = self.normalize_content(message)

        if role == "assistant":
            # Render markdown for assistant messages
            if self.logger:
                self.logger.info(f"ASSISTANT: {text_content}")
            try:
                if text_content.strip():
                    self.console.print(Markdown(text_content))
            except Exception:
                self.console.print(text_content)
        elif role == "system":
            if self.logger:
                self.logger.info(f"SYSTEM: {text_content}")
            self.console.print(f"[bold blue]System:[/bold blue] {text_content}")
        elif role == "error":
            if self.logger:
                self.logger.error(f"ERROR: {text_content}")
            self.console.print(f"[bold red]Error:[/bold red] {text_content}")
        else:
            if self.logger:
                self.logger.info(f"USER: {text_content}")
            self.console.print(f"[bold green]User:[/bold green] {text_content}")
        
        import sys
        sys.stdout.flush()
    
    def print_tool_call(self, tool_name: str, args: dict):
        """Display tool call"""
        args_str = ", ".join(f"[cyan]{k}[/cyan]=[green]{v}[/green]" for k, v in args.items())
        if self.logger:
            self.logger.info(f"TOOL CALL: {tool_name}({args})")
        self.console.print(
            f"[bold yellow]⚙ Executing tool:[/bold yellow] [bold magenta]{tool_name}[/bold magenta]({args_str})"
        )
        import sys
        sys.stdout.flush()
    
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
            self.console.print(Panel(syntax, title=f"Diff: {filename}", border_style="yellow"))
    
    async def request_approval(self, action: str, details: str) -> str:
        """Request human approval for action"""
        panel = Panel(
            f"[bold]Action:[/bold] {action}\n\n[dim]{details}[/dim]\n\n"
            "[bold green][1] Approve[/bold green]  [bold yellow][2] Edit[/bold yellow]  [bold red][3] Reject[/bold red]",
            title="Approval Required",
            border_style="yellow"
        )
        self.console.print(panel)
        
        choice = (await self.prompt_simple("[bold]Choice [1-3]: [/bold]")).strip()
        
        if choice == "1":
            return "approve"
        elif choice == "2":
            return "edit"
        else:
            return "reject"

    async def request_tool_approval(self, tool_name: str, args: dict) -> str:
        """
        Request approval for sensitive tool execution using interactive menu.
        Returns: 'allow_once', 'allow_all', or 'deny'
        """
        import json
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        args_json = json.dumps(args, indent=2)
        
        panel = Panel(
            f"[bold red]⚠️  Security Alert: Agent wants to execute a sensitive command[/bold red]\n\n"
            f"[bold cyan]Tool:[/bold cyan] {tool_name}\n"
            f"[bold cyan]Arguments:[/bold cyan]\n{args_json}\n",
            title="Security Check",
            border_style="red"
        )
        self.console.print(panel)
        
        choices = [
            Choice(value="allow_once", name="Allow once"),
            Choice(value="allow_all", name="Allow this tool for session"),
            Choice(value="deny", name="Deny"),
        ]
        
        # Use InquirerPy's async execution
        result = await inquirer.select(
            message="Select action:",
            choices=choices,
            default="deny",
            qmark="?",
        ).execute_async()
        
        return result
    
    def show_progress(self, message: str):
        """Show progress indicator"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        )
    
    def update_token_count(self, tokens: int):
        """Update and display token count"""
        self.total_tokens += tokens
        # We don't always want to print this to keep the UI clean
        # self.console.print(f"[dim]Tokens: {tokens:,} (Total: {self.total_tokens:,})[/dim]")
