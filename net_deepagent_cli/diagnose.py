import sys
import os
import socket
import subprocess
import importlib
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def check_python_version():
    console.print("\n[bold cyan]1. Checking Python Environment[/bold cyan]")
    version = sys.version_info
    if version.major == 3 and version.minor >= 12:
        console.print(f"[green]✓ Python version {version.major}.{version.minor}.{version.micro} is supported.[/green]")
        return True
    else:
        console.print(f"[red]✗ Python version 3.12+ is required. Found {version.major}.{version.minor}.{version.micro}.[/red]")
        return False

def check_dependencies():
    console.print("\n[bold cyan]2. Checking Core Dependencies[/bold cyan]")
    deps = ["langchain", "mcp", "fastmcp", "streamlit", "discord", "rich"]
    all_passed = True
    for dep in deps:
        try:
            importlib.import_module(dep)
            console.print(f"[green]✓ {dep} is installed.[/green]")
        except ImportError:
            console.print(f"[red]✗ Missing dependency: {dep}[/red]")
            all_passed = False
    return all_passed

def check_system_utilities():
    console.print("\n[bold cyan]3. Checking System Utilities[/bold cyan]")
    all_passed = True
    
    # Check SQLite
    try:
        subprocess.run(["sqlite3", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        console.print("[green]✓ sqlite3 is installed.[/green]")
    except Exception:
        console.print("[yellow]! sqlite3 is not available in PATH.[/yellow]")
        all_passed = False

    # Check RabbitMQ
    try:
        result = subprocess.run(["systemctl", "is-active", "rabbitmq-server"], capture_output=True, text=True)
        if result.stdout.strip() == "active":
            console.print("[green]✓ rabbitmq-server is active and running.[/green]")
        else:
            console.print("[red]✗ rabbitmq-server is not active.[/red]")
            all_passed = False
    except Exception:
        console.print("[yellow]! Unable to check rabbitmq-server status (systemctl failed).[/yellow]")
        all_passed = False

    return all_passed

def check_firewall():
    console.print("\n[bold cyan]4. Checking Firewall Status[/bold cyan]")
    try:
        # Check UFW
        result = subprocess.run(["sudo", "ufw", "status"], capture_output=True, text=True)
        if "Status: active" in result.stdout:
            console.print("[yellow]! UFW firewall is ACTIVE. Please ensure required ports are allowed.[/yellow]")
        elif "Status: inactive" in result.stdout:
            console.print("[green]✓ UFW firewall is INACTIVE.[/green]")
        else:
            console.print("[dim]UFW not found or requires sudo password.[/dim]")
    except Exception:
        pass
        
    try:
        # Check Firewalld
        result = subprocess.run(["systemctl", "is-active", "firewalld"], capture_output=True, text=True)
        if result.stdout.strip() == "active":
            console.print("[yellow]! Firewalld is ACTIVE. Please ensure required ports are allowed.[/yellow]")
        else:
            console.print("[green]✓ Firewalld is INACTIVE.[/green]")
    except Exception:
        pass

def check_ports():
    console.print("\n[bold cyan]5. Checking Required Ports[/bold cyan]")
    ports = {
        8000: "MCP Server (Primary)",
        8001: "MCP Server (Secondary)",
        8501: "Streamlit UI",
        5672: "RabbitMQ"
    }
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Port")
    table.add_column("Service")
    table.add_column("Status")

    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            status = "[green]In Use / Listening[/green]"
        else:
            status = "[yellow]Not Listening[/yellow] (or blocked)"
        table.add_row(str(port), name, status)
        sock.close()
        
    console.print(table)
    console.print("[dim]Note: 'Not Listening' is fine if the service is currently stopped. If the service is running, it may indicate a firewall issue.[/dim]")

def check_credentials():
    console.print("\n[bold cyan]6. Checking Credentials[/bold cyan]")
    creds_path = os.path.expanduser("~/.net-deepagent/creds.json")
    if os.path.exists(creds_path):
        if os.access(creds_path, os.R_OK):
            console.print(f"[green]✓ Credentials file found and readable: {creds_path}[/green]")
        else:
            console.print(f"[red]✗ Credentials file found but NOT readable: {creds_path}[/red]")
    else:
        console.print(f"[yellow]! Credentials file not found: {creds_path}. Agent integrations may fail.[/yellow]")

def check_mcp_servers():
    console.print("\n[bold cyan]7. Checking MCP Servers[/bold cyan]")
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if "mcp_servers.py" in result.stdout:
            console.print("[green]✓ mcp_servers.py process is currently running.[/green]")
        else:
            console.print("[yellow]! mcp_servers.py is not running. (Use 'workerxy mcp' to start)[/yellow]")
    except Exception:
        console.print("[dim]Unable to check process list.[/dim]")

def main():
    console.print(Panel.fit("[bold blue]WorkerXY Diagnostic Tool[/bold blue]", border_style="blue"))
    
    check_python_version()
    check_dependencies()
    check_system_utilities()
    check_firewall()
    check_ports()
    check_credentials()
    check_mcp_servers()
    
    console.print("\n[bold green]Diagnosis Complete![/bold green]\n")

if __name__ == "__main__":
    main()
