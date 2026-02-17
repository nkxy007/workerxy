from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from pathlib import Path
import difflib

class TerminalUI:
    """Rich terminal interface for agent interaction"""
    
    def __init__(self, agent_name: str):
        self.console = Console(force_terminal=True, force_interactive=False)
        self.agent_name = agent_name
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.history_file = self.config_dir / "history"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = PromptSession(
            history=FileHistory(str(self.history_file))
        )
        
        # Define commands with descriptions for autocompletion
        self.command_meta = {
            "/help": "Show available commands",
            "/clear": "Clear conversation history",
            "/save": "Save current context to session",
            "/resume": "Resume a saved session",
            "/sessions": "List all saved sessions",
            "/tokens": "Show token usage",
            "/context": "Analyze current context",
            "/skills": "Manage and list skills",
            "/agents": "Show available A2A agents",
            "/automata": "Manage background tasks",
            "/memory": "Show current agent memory",
            "/exit": "Exit the CLI"
        }
        self.completer = WordCompleter(
            list(self.command_meta.keys()),
            meta_dict=self.command_meta,
            ignore_case=True,
            match_middle=True
        )
        
        # Token tracking
        self.total_tokens = 0
        
    def print_banner(self):
        """Display startup banner with CoworkerX Networking word art"""
        # https://patorjk.com/software/taag/#p=display&f=Isometric1&t=WorkerXY%0ANetworking&x=none&v=4&h=4&w=80&we=false
        art = r"""
   ______                                __             _  __
  / ____/___ _      ______  ________  / /_____  _____| |/ /
 / /   / __ \ | /| / / __ \/ ___/ _ \/ //_/ _ \/ ___/|   / 
/ /___/ /_/ / |/ |/ / /_/ / /  /  __/ ,< /  __/ /   /   |  
\____/\____/|__/|__/\____/_/   \___/_/|_|\___/_/   /_/|_|  
                                                           
    _   __     __                      __    _             
   / | / /__  / /__      ______  _____/ /__ (_)___  ____ _ 
  /  |/ / _ \/ __/ | /| / / __ \/ ___/ //_// / __ \/ __ `/ 
 / /|  /  __/ /_ | |/ |/ / /_/ / /  / ,<  / / / / / /_/ /  
/_/ |_/\___/\__/ |__/|__/\____/_/  /_/|_|/_/_/ /_/\__, /   
                                                  /____/   
"""
        art = r"""
              ___           ___           ___           ___           ___           ___           ___           ___                               
     /\__\         /\  \         /\  \         /\__\         /\  \         /\  \         |\__\         |\__\                              
    /:/ _/_       /::\  \       /::\  \       /:/  /        /::\  \       /::\  \        |:|  |        |:|  |                             
   /:/ /\__\     /:/\:\  \     /:/\:\  \     /:/__/        /:/\:\  \     /:/\:\  \       |:|  |        |:|  |                             
  /:/ /:/ _/_   /:/  \:\  \   /::\~\:\  \   /::\__\____   /::\~\:\  \   /::\~\:\  \      |:|__|__      |:|__|__                           
 /:/_/:/ /\__\ /:/__/ \:\__\ /:/\:\ \:\__\ /:/\:::::\__\ /:/\:\ \:\__\ /:/\:\ \:\__\ ____/::::\__\     /::::\__\                          
 \:\/:/ /:/  / \:\  \ /:/  / \/_|::\/:/  / \/_|:|~~|~    \:\~\:\ \/__/ \/_|::\/:/  / \::::/~~/~       /:/~~/~                             
  \::/_/:/  /   \:\  /:/  /     |:|::/  /     |:|  |      \:\ \:\__\      |:|::/  /   ~~|:|~~|       /:/  /                               
   \:\/:/  /     \:\/:/  /      |:|\/__/      |:|  |       \:\ \/__/      |:|\/__/      |:|  |       \/__/                                
    \::/  /       \::/  /       |:|  |        |:|  |        \:\__\        |:|  |        |:|  |                                            
     \/__/         \/__/         \|__|         \|__|         \/__/         \|__|         \|__|                                            
      ___           ___           ___           ___           ___           ___           ___                       ___           ___     
     /\__\         /\  \         /\  \         /\__\         /\  \         /\  \         /\__\          ___        /\__\         /\  \    
    /::|  |       /::\  \        \:\  \       /:/ _/_       /::\  \       /::\  \       /:/  /         /\  \      /::|  |       /::\  \   
   /:|:|  |      /:/\:\  \        \:\  \     /:/ /\__\     /:/\:\  \     /:/\:\  \     /:/__/          \:\  \    /:|:|  |      /:/\:\  \  
  /:/|:|  |__   /::\~\:\  \       /::\  \   /:/ /:/ _/_   /:/  \:\  \   /::\~\:\  \   /::\__\____      /::\__\  /:/|:|  |__   /:/  \:\  \ 
 /:/ |:| /\__\ /:/\:\ \:\__\     /:/\:\__\ /:/_/:/ /\__\ /:/__/ \:\__\ /:/\:\ \:\__\ /:/\:::::\__\  __/:/\/__/ /:/ |:| /\__\ /:/__/_\:\__\
 \/__|:|/:/  / \:\~\:\ \/__/    /:/  \/__/ \:\/:/ /:/  / \:\  \ /:/  / \/_|::\/:/  / \/_|:|~~|~    /\/:/  /    \/__|:|/:/  / \:\  /\ \/__/
     |:/:/  /   \:\ \:\__\     /:/  /       \::/_/:/  /   \:\  /:/  /     |:|::/  /     |:|  |     \::/__/         |:/:/  /   \:\ \:\__\  
     |::/  /     \:\ \/__/     \/__/         \:\/:/  /     \:\/:/  /      |:|\/__/      |:|  |      \:\__\         |::/  /     \:\/:/  /  
     /:/  /       \:\__\                      \::/  /       \::/  /       |:|  |        |:|  |       \/__/         /:/  /       \::/  /   
     \/__/         \/__/                       \/__/         \/__/         \|__|         \|__|                     \/__/         \/__/    
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
    
    async def get_user_input(self):
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
    
    def print_message(self, message: str, role: str = "assistant"):
        """Print a message with formatting"""
        if role == "assistant":
            # Render markdown for assistant messages
            try:
                self.console.print(Markdown(message))
            except:
                self.console.print(message)
        elif role == "system":
            self.console.print(f"[bold blue]System:[/bold blue] {message}")
        elif role == "error":
            self.console.print(f"[bold red]Error:[/bold red] {message}")
        else:
            self.console.print(f"[bold green]User:[/bold green] {message}")
        
        import sys
        sys.stdout.flush()
    
    def print_tool_call(self, tool_name: str, args: dict):
        """Display tool call"""
        args_str = ", ".join(f"[cyan]{k}[/cyan]=[green]{v}[/green]" for k, v in args.items())
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
    
    def request_approval(self, action: str, details: str) -> str:
        """Request human approval for action"""
        panel = Panel(
            f"[bold]Action:[/bold] {action}\n\n[dim]{details}[/dim]\n\n"
            "[bold green][1] Approve[/bold green]  [bold yellow][2] Edit[/bold yellow]  [bold red][3] Reject[/bold red]",
            title="Approval Required",
            border_style="yellow"
        )
        self.console.print(panel)
        
        choice = self.console.input("[bold]Choice [1-3]: [/bold]").strip()
        
        if choice == "1":
            return "approve"
        elif choice == "2":
            return "edit"
        else:
            return "reject"

    def request_tool_approval(self, tool_name: str, args: dict) -> str:
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
        
        # Use InquirerPy for interactive selection
        # Note: We use .execute() to run it synchronously
        result = inquirer.select(
            message="Select action:",
            choices=choices,
            default="deny",
            qmark="?",
        ).execute()
        
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
