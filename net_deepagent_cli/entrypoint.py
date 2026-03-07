import sys
import asyncio

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ["cli", "headless"]:
        print("Usage: workerxy {cli,headless} [options]")
        sys.exit(1)

    command = sys.argv.pop(1)  # Remove the subcommand so existing parsers work cleanly

    if command == "cli":
        from net_deepagent_cli.cli import main as cli_main
        cli_main()
    elif command == "headless":
        from net_deepagent_cli.headless import run_headless, logger
        try:
            asyncio.run(run_headless())
        except KeyboardInterrupt:
            # Matches existing headless.py behavior
            logger.info("Headless agent stopped by user.")

if __name__ == "__main__":
    main()
