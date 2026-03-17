import sys
import asyncio
import subprocess
import os
import logging
from warnings import filterwarnings

logger = logging.getLogger(__name__)

filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=RuntimeWarning)
# ignore typing.NotRequired
filterwarnings("ignore", category=FutureWarning)
filterwarnings("ignore", category=UserWarning)


def main():
    valid_commands = ["cli", "headless", "discord", "ui", "mcp", "skill", "diagnose"]
    if len(sys.argv) < 2 or sys.argv[1] not in valid_commands:
        print(f"Usage: workerxy {{{','.join(valid_commands)}}} [options]")
        sys.exit(1)

    command = sys.argv.pop(1)  # Remove the subcommand so existing parsers work cleanly

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if command == "cli":
        from net_deepagent_cli.cli import main as cli_main
        cli_main()
    elif command == "headless":
        from net_deepagent_cli.headless import run_headless, logger as headless_logger
        try:
            asyncio.run(run_headless())
        except KeyboardInterrupt:
            # Matches existing headless.py behavior
            headless_logger.info("Headless agent stopped by user.")
    elif command == "discord":
        try:
            from net_deepagent_cli.communication.discord_bot import main as discord_main
            discord_main()
        except KeyboardInterrupt:
            # Matches existing discord.py behavior
            logger.info("Discord bot stopped by user.")
    elif command == "ui":
        try:
            ui_app_path = os.path.join(project_root, "ui", "app.py")
            subprocess.run(["streamlit", "run", ui_app_path] + sys.argv[1:], cwd=project_root)
        except KeyboardInterrupt:
            # Matches existing streamlit behavior
            logger.info("Streamlit app stopped by user.")
    elif command == "mcp":
        try:
            mcp_servers_path = os.path.join(project_root, "mcp_servers.py")
            subprocess.run([sys.executable, mcp_servers_path] + sys.argv[1:], cwd=project_root)
        except KeyboardInterrupt:
            # Matches existing mcp_servers.py behavior
            logger.info("MCP servers stopped by user.")
    elif command == "skill":
        try:
            skill_cli_path = os.path.join(project_root, "utils", "skill_manager", "cli.py")
            subprocess.run([sys.executable, skill_cli_path] + sys.argv[1:], cwd=project_root)
        except KeyboardInterrupt:
            logger.info("Skill manager stopped by user.")
    elif command == "diagnose":
        try:
            from net_deepagent_cli.diagnose import main as diagnose_main
            diagnose_main()
        except KeyboardInterrupt:
            logger.info("Diagnostic tool stopped by user.")


if __name__ == "__main__":
    main()
