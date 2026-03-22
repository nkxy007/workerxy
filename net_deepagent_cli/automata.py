import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from prompt_toolkit.completion import WordCompleter
from langchain_core.messages import HumanMessage
from net_deepagent_cli.ui import HierarchicalCompleter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automata")

class AutomataManager:
    """Manages scheduled tasks for the agent"""
    
    def __init__(self, agent_name: str, agent_instance):
        self.agent_name = agent_name
        self.agent = agent_instance
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.tasks_file = self.config_dir / "automata.json"
        
        # Scheduler
        self.scheduler = AsyncIOScheduler()
        self.tasks: Dict[str, Any] = {}
        
        # Ensure config dir exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.logs_dir = self.config_dir / "automata_results"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load tasks
        self.load_tasks()

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Automata scheduler started")

    def stop(self):
        """Stop the scheduler and mark tasks as stale"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        # Mark all enabled tasks as stale so they don't auto-run next time
        self.mark_tasks_stale()

    def mark_tasks_stale(self):
        """Mark all currently enabled tasks as stale"""
        changed = False
        for task_id, task in self.tasks.items():
            if task.get("enabled", True):
                task["enabled"] = False
                task["stale"] = True
                task["last_status"] = "Stale (Stopped on Exit)"
                changed = True
        
        if changed:
            self.save_tasks()

    def load_tasks(self):
        """Load tasks from disk and reschedule them"""
        if self.tasks_file.exists():
            try:
                data = json.loads(self.tasks_file.read_text())
                for task_id, task_info in data.items():
                    # Only schedule if enabled (which they won't be if stale)
                    self.schedule_task_internal(task_id, task_info)
                self.tasks = data
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")

    def save_tasks(self):
        """Save tasks to disk"""
        try:
            self.tasks_file.write_text(json.dumps(self.tasks, indent=2))
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
            
    def save_task_result(self, task_id: str, result_content: str):
        """Save execution result to a markdown file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_id}_{timestamp}.md"
        filepath = self.logs_dir / filename
        
        try:
            # Create a nice markdown report
            prompt = self.tasks[task_id].get("prompt", "Unknown Task")
            report = (
                f"# Automata Execution Report\n"
                f"**Task ID:** {task_id}\n"
                f"**Date:** {datetime.now()}\n"
                f"**Prompt:** {prompt}\n\n"
                f"## Result\n\n"
                f"{result_content}\n"
            )
            filepath.write_text(report)
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to save result for task {task_id}: {e}")
            return None

    def get_task_logs(self, task_id: str) -> List[Path]:
        """Get list of log files for a task"""
        if not self.logs_dir.exists():
            return []
        return sorted(self.logs_dir.glob(f"{task_id}_*.md"), reverse=True)

    def read_log(self, filename: str) -> str:
        """Read content of a log file"""
        filepath = self.logs_dir / filename
        if filepath.exists() and filepath.parent == self.logs_dir:
             return filepath.read_text()
        return "Log file not found."

    def add_task(self, prompt: str, interval_seconds: int = 0, cron: str = None, end_time: str = None, run_immediately: bool = True) -> str:
        """Add a new task"""
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task_info = {
            "id": task_id,
            "prompt": prompt,
            "created_at": str(datetime.now()),
            "interval_seconds": interval_seconds,
            "cron": cron,
            "end_time": end_time,
            "enabled": True
        }
        
        self.schedule_task_internal(task_id, task_info, is_new=run_immediately)
        self.tasks[task_id] = task_info
        self.save_tasks()
        return task_id

    def remove_task(self, task_id: str):
        """Remove a task"""
        if task_id in self.tasks:
            try:
                self.scheduler.remove_job(task_id)
            except Exception:
                pass # Job might not exist if disabled or error
            del self.tasks[task_id]
            self.save_tasks()
            return True
        return False

    def stop_task(self, task_id: str):
        """Stop/Disable a task without removing it"""
        if task_id in self.tasks:
            try:
                self.scheduler.remove_job(task_id)
            except Exception:
                pass # Job might not exist if already disabled
            self.tasks[task_id]["enabled"] = False
            self.tasks[task_id]["stale"] = False
            self.tasks[task_id]["last_status"] = "Stopped"
            self.save_tasks()
            return True
        return False
        
    def resume_task(self, task_id: str):
        """Resume a stale/disabled task"""
        if task_id in self.tasks:
            self.tasks[task_id]["enabled"] = True
            self.tasks[task_id]["stale"] = False
            self.tasks[task_id]["last_status"] = "Resumed"
            self.schedule_task_internal(task_id, self.tasks[task_id])
            self.save_tasks()
            return True
        return False

    def schedule_task_internal(self, task_id: str, task_info: Dict, is_new: bool = False):
        """Internal method to add job to APScheduler"""
        if not task_info.get("enabled", True):
            return

        # Check if expired
        end_time_str = task_info.get("end_time")
        end_date = None
        if end_time_str:
            try:
                end_date = datetime.fromisoformat(end_time_str)
                if end_date < datetime.now():
                    logger.info(f"Task {task_id} has expired (End Time: {end_time_str}). Not scheduling.")
                    task_info["enabled"] = False
                    task_info["stale"] = True
                    task_info["last_status"] = "Expired"
                    return
            except Exception as e:
                logger.error(f"Failed to parse end_time for task {task_id}: {e}")

        trigger = None
        if task_info.get("interval_seconds", 0) > 0:
            trigger = IntervalTrigger(seconds=task_info["interval_seconds"], end_date=end_date)
        # TODO: Add cron support parsing if needed
        elif task_info.get("cron"):
             # Simple cron string support if needed later
             pass
        
        if trigger:
            job_kwargs = {
                "trigger": trigger,
                "id": task_id,
                "args": [task_info["prompt"], task_id],
                "replace_existing": True
            }
            if is_new:
                job_kwargs["next_run_time"] = datetime.now()
                
            self.scheduler.add_job(
                self.execute_agent_task,
                **job_kwargs
            )

    def _normalize_content(self, msg_content: Any) -> str:
        """Normalize message content to string (handles list of blocks)"""
        if isinstance(msg_content, list):
            text_parts = []
            for block in msg_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
                elif hasattr(block, "text"): # Support for some objects
                    text_parts.append(getattr(block, "text"))
            return "".join(text_parts)
        return str(msg_content) if msg_content is not None else ""

    async def execute_agent_task(self, prompt: str, task_id: str):
        """Execute the agent task"""
        logger.info(f"Executing Automata Task {task_id}: {prompt}")
        
        try:
             # Prepare input for the agent
             inputs = {"messages": [HumanMessage(content=prompt)]}
             result = await self.agent.ainvoke(inputs)
             
             # Extract content
             content = "No output."
             if "messages" in result:
                 last_msg = result["messages"][-1]
                 content = self._normalize_content(last_msg.content)
                 logger.info(f"Task {task_id} completed. Result: {content[:50]}...")
             
             # Save result to file
             self.save_task_result(task_id, content)
             
             # Save "last_run" status
             self.tasks[task_id]["last_run"] = str(datetime.now())
             self.tasks[task_id]["last_status"] = "success"
             self.save_tasks()
             
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.tasks[task_id]["last_status"] = f"error: {str(e)}"
            self.save_tasks()

    async def get_agent_help_for_parsing(self, user_input: str) -> Dict[str, Any]:
        """Ask the agent to parse the user input into prompt, interval, and optional end_time"""
        try:
            now = datetime.now().isoformat()
            # We construct a specific prompt for the agent to act as a parser
            parsing_prompt = (
                f"You are a parser helper. The user wants to schedule a task.\n"
                f"Current Time: {now}\n"
                f"User Input: '{user_input}'\n"
                f"Extract the task description, the interval in seconds, and an optional end_time.\n"
                f"Return ONLY a JSON object with keys:\n"
                f"- 'prompt' (str): The task to perform.\n"
                f"- 'interval_seconds' (int): How often to run it (0 if not specified).\n"
                f"- 'end_time' (str, optional): ISO 8601 timestamp when the task should stop (null if not specified).\n"
                f"- 'run_immediately' (bool): True if the task should run immediately right now, False otherwise (default True).\n"
                f"If the user says 'for 5 hours', calculate the end_time based on the Current Time.\n"
                f"If the user says 'till 1:30', assume the next occurrence of 1:30 AM/PM and return the ISO timestamp.\n"
                f"Example JSON: {{\"prompt\": \"check ping\", \"interval_seconds\": 60, \"end_time\": \"2024-05-20T15:00:00\", \"run_immediately\": true}}"
            )
            
            # Use raw LLM if available to bypass tool-calling loop when parsing text
            llm = getattr(self.agent, "raw_llm", None)
            
            if llm:
                result = await llm.ainvoke([HumanMessage(content=parsing_prompt)])
                content = result.content
                if hasattr(content, "text"):
                    content = content.text
            else:
                inputs = {"messages": [HumanMessage(content=parsing_prompt)]}
                result = await self.agent.ainvoke(inputs)
                if "messages" in result:
                    last_msg = result["messages"][-1]
                    content = self._normalize_content(last_msg.content)
                else:
                    return {}
                
                # Cleanup potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                    
                import json
                return json.loads(content)
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return {}
        return {}

    def list_tasks(self) -> List[Dict]:
        """List tasks, sorted by active status first"""
        tasks_list = list(self.tasks.values())
        # Sort: Enabled (True) -> Disabled (False). 
        # Since False < True, and we want True first, we use reverse=True on the boolean key
        tasks_list.sort(key=lambda t: t.get("enabled", False), reverse=True)
        return tasks_list

async def process_automata_command(manager: AutomataManager, command: str, ui) -> bool:
    """
    Process a single automata command line. 
    Returns True if command was handled, False if unknown.
    """
    import re
    
    parts = command.split()
    if not parts:
        return True
        
    cmd = parts[0].lower()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    
    # Handle 'help'
    if cmd == "help":
        ui.console.print(
            "\n[bold]Commands:[/bold]\n"
            "  [green]list[/green]                        List all tasks\n"
            "  [green]add <prompt> every <N> <unit>[/green]   Add a task (e.g., 'add check ping every 5 minutes')\n"
            "  [green]<prompt> every <N> <unit>[/green]       Implicit add (e.g., 'check ping every 10min')\n"
            "  [green]remove <id>[/green]                  Remove a task by ID\n"
            "  [green]stop <id>[/green]                    Stop a task without removing it\n"
            "  [green]resume <id>[/green]                  Resume a stopped/stale task\n"
            "  [green]logs <id>[/green]                    List logs for a task\n"
            "  [green]view <filename>[/green]              View a specific log file\n"
            "  [green]back[/green]                        Return to main menu\n"
        )
        return True

    # Handle 'list'
    if cmd == "list":
        tasks = manager.list_tasks()
        if not tasks:
            ui.console.print("[dim]No tasks scheduled.[/dim]")
        else:
            from rich.table import Table
            table = Table(title="Scheduled Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Prompt", style="white")
            table.add_column("Interval", style="green")
            table.add_column("End Time", style="blue")
            table.add_column("Last Run", style="yellow")
            table.add_column("Status", style="magenta")
            
            for t in tasks:
                interval_s = t.get("interval_seconds", 0)
                if interval_s >= 3600:
                    interval_str = f"{interval_s/3600:.1f}h"
                elif interval_s >= 60:
                    interval_str = f"{interval_s/60:.1f}m"
                else:
                    interval_str = f"{interval_s}s"
                
                # Format end_time nicely
                end_time_raw = t.get("end_time")
                if end_time_raw:
                    try:
                        # Try to make it a bit more readable
                        dt = datetime.fromisoformat(end_time_raw)
                        end_time_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        end_time_str = end_time_raw
                else:
                    end_time_str = "[dim]Forever[/dim]"

                status = t.get("last_status", "Unknown")
                status_style = "magenta"
                
                if not t.get("enabled", True):
                    # Check if explicit stale flag
                    if t.get("stale", False):
                        status = "STALE (Stopped)"
                        status_style = "dim yellow"
                        if t.get("last_status") == "Expired":
                            status = "EXPIRED"
                            status_style = "dim red"
                    else:
                        status = "DISABLED"
                        status_style = "dim"
                    
                table.add_row(
                    t["id"],
                    t["prompt"],
                    interval_str,
                    end_time_str,
                    t.get("last_run", "Never"),
                    f"[{status_style}]{status}[/{status_style}]"
                )
            ui.console.print(table)
        return True

    # Handle 'logs'
    if cmd == "logs":
        if len(parts) < 2:
            ui.console.print("[red]Usage: logs <id>[/red]")
            return True
        task_id = parts[1]
        logs = manager.get_task_logs(task_id)
        
        if not logs:
             ui.console.print(f"[dim]No logs found for task {task_id}.[/dim]")
        else:
            from rich.table import Table
            table = Table(title=f"Execution Logs for {task_id}")
            table.add_column("Filename", style="cyan")
            table.add_column("Size", style="dim")
            
            for p in logs:
                size_kb = f"{p.stat().st_size / 1024:.1f} KB"
                table.add_row(p.name, size_kb)
            ui.console.print(table)
        return True

    # Handle 'view'
    if cmd == "view":
        if len(parts) < 2:
            ui.console.print("[red]Usage: view <filename>[/red]")
            return True
        filename = parts[1]
        content = manager.read_log(filename)
        from rich.markdown import Markdown
        from rich.panel import Panel
        ui.console.print(Panel(Markdown(content), title=filename, border_style="blue"))
        return True

    # Handle 'resume'
    if cmd == "resume":
        if len(parts) < 2:
            ui.console.print("[red]Usage: resume <id>[/red]")
            return True
        task_id = parts[1]
        if manager.resume_task(task_id):
            ui.console.print(f"[green]Task {task_id} resumed.[/green]")
        else:
            ui.console.print(f"[red]Task {task_id} not found.[/red]")
        return True

    # Handle 'stop'
    if cmd == "stop":
        if len(parts) < 2:
            ui.console.print("[red]Usage: stop <id>[/red]")
            return True
        task_id = parts[1]
        if manager.stop_task(task_id):
            ui.console.print(f"[green]Task {task_id} stopped.[/green]")
        else:
            ui.console.print(f"[red]Task {task_id} not found.[/red]")
        return True

    # Handle 'remove'
    if cmd == "remove":
        if len(parts) < 2:
            ui.console.print("[red]Usage: remove <id>[/red]")
            return True
        task_id = parts[1]
        if manager.remove_task(task_id):
            ui.console.print(f"[green]Task {task_id} removed.[/green]")
        else:
            ui.console.print(f"[red]Task {task_id} not found.[/red]")
        return True

    # Handle 'add' or implicit add
    
    # 1. Try robust regex parsing logic for intervals
    # Pattern looks for "every <digits><optional space><unit>"
    # Matches: "every 5min", "every 5 min", "every 5 minutes", "every 5"
    interval_regex = r"every\s+(\d+)\s*([a-zA-Z]*)"
    match = re.search(interval_regex, command, re.IGNORECASE)
    
    prompt = None
    interval = 0
    run_imm = True
    
    if match:
        val = int(match.group(1))
        unit_str = match.group(2).lower()
        
        # Determine seconds
        if unit_str.startswith("min") or unit_str == "m":
            interval = val * 60
        elif unit_str.startswith("hour") or unit_str == "h":
            interval = val * 3600
        else:
            # Default to seconds if "sec" or empty
            interval = val
            
        # Extract prompt by removing the "every X Y" part
        # We replace the matched string with empty, and clean up "add"
        prompt_raw = command[:match.start()] + command[match.end():]
        prompt_parts = prompt_raw.split()
        if prompt_parts and prompt_parts[0].lower() == "add":
            prompt_parts = prompt_parts[1:]
        prompt = " ".join(prompt_parts).strip()
        
    # 2. If regex fail or prompt empty, or contains duration/end keywords, try LLM fallback
    # This allows the LLM to handle complex timelines like "for 5 hours" or "till 1:30"
    if not prompt or interval == 0 or any(kw in command.lower() for kw in ["for", "till", "until", "duration"]):
         ui.console.print("[dim]Parsing with agent intelligence...[/dim]")
         parsed = await manager.get_agent_help_for_parsing(command)
         if parsed and "prompt" in parsed and "interval_seconds" in parsed:
             prompt = parsed["prompt"]
             interval = parsed["interval_seconds"]
             run_imm = parsed.get("run_immediately", True)
    
    if prompt and interval > 0:
        end_time = None
        if 'parsed' in locals() and parsed:
            end_time = parsed.get("end_time")
            
        task_id = manager.add_task(prompt, interval_seconds=interval, end_time=end_time, run_immediately=run_imm)
        end_str = f", End: {end_time}" if end_time else ""
        ui.console.print(f"[green]Task added with ID {task_id} (Interval: {interval}s{end_str})[/green]")
        return True
    
    if "every" in command:
         ui.console.print("[red]Could not parse command even with agent help. Please specify 'every <N> <unit>' clearly.[/red]")
         return True

    return False # Unknown command

async def handle_automata_ui(ui, manager: AutomataManager):
    """Interactive loop for Automata management"""
    ui.console.print("\n[bold magenta]=== Automata Mode ===[/bold magenta]")
    # Define structure for HierarchicalCompleter
    automata_structure = {
        "help": {"desc": "Show automata commands"},
        "list": {"desc": "List all scheduled tasks"},
        "add": {"desc": "Add a new background task"},
        "remove": {"desc": "Remove a task by ID"},
        "stop": {"desc": "Stop a task by ID"},
        "resume": {"desc": "Resume a stopped/stale task"},
        "logs": {"desc": "List execution logs for a task"},
        "view": {"desc": "View a specific log file"},
        "back": {"desc": "Return to main agent prompt"}
    }
    
    # Also support slash commands within automata mode
    for cmd in list(automata_structure.keys()):
        automata_structure["/" + cmd] = automata_structure[cmd]
        
    completer = HierarchicalCompleter(automata_structure)
    
    while True:
        try:
            user_input = await ui.session.prompt_async(
                "automata> ",
                completer=completer
            )
            user_input = user_input.strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["back", "exit", "quit"]:
                break
            
            handled = await process_automata_command(manager, user_input, ui)
            if not handled:
                ui.console.print(f"[red]Unknown command. Type 'help'.[/red]")
                
        except (KeyboardInterrupt, EOFError):
            break
            
    ui.console.print("[bold magenta]Exiting Automata Mode...[/bold magenta]\n")
