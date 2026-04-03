"""
automata_tools.py
-----------------
LangChain @tool wrappers that expose the AutomataManager to the main agent.

The module holds a module-level reference to the live AutomataManager instance.
Call `set_automata_manager(mgr)` once at startup (from loop.py) to wire it.
The main agent can then use these tools to create / manage automata jobs
programmatically from tickets or user requests.

Note: The existing /automata CLI commands in loop.py are unaffected.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from langchain_core.tools import tool

if TYPE_CHECKING:
    from net_deepagent_cli.automata import AutomataManager

logger = logging.getLogger("automata_tools")

# ---------------------------------------------------------------------------
# Module-level shared reference — set once in loop.py after the manager
# is instantiated and started.
# ---------------------------------------------------------------------------
_automata_manager: Optional["AutomataManager"] = None


def set_automata_manager(manager: "AutomataManager") -> None:
    """Wire the live AutomataManager into the tools module.

    Called from net_deepagent_cli/loop.py immediately after
    `automata_manager.start()`.
    """
    global _automata_manager
    _automata_manager = manager
    logger.info("AutomataManager reference set in automata_tools.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def automata_create_job(
    prompt: str,
    interval_seconds: int,
    end_time: Optional[str] = None,
    run_immediately: bool = True,
) -> str:
    """Create a new background automata (scheduled job) that the agent will run repeatedly.

    Use this tool when a ticket or user requests a periodic / recurring task
    such as "ping 8.8.8.8 every 1 hour for 4 hours" or
    "check CPU usage every 15 minutes until midnight".

    You MUST convert any natural language time expression to concrete values
    BEFORE calling this tool:
      - interval_seconds: the repeat period in seconds (e.g. 1 hour → 3600)
      - end_time: ISO-8601 UTC datetime string for when the job should stop,
                  or None if it should run indefinitely.

    Args:
        prompt: The task instruction the agent will execute on each run.
                Should be a self-contained, actionable prompt
                (e.g. "ping 8.8.8.8 and report latency").
        interval_seconds: How often to run the job, in seconds. Must be > 0.
        end_time: Optional ISO-8601 datetime string when the job expires
                  (e.g. "2026-03-22T23:00:00"). Pass None to run forever.
        run_immediately: True to trigger the job immediately upon creation,
                         False to wait for the first interval to elapse.

    Returns:
        A confirmation string with the new task ID, or an error description.
    """
    if _automata_manager is None:
        return (
            "Error: AutomataManager is not available. "
            "The automata system may not have been initialised yet."
        )

    if interval_seconds <= 0:
        return f"Error: interval_seconds must be > 0, got {interval_seconds}."

    try:
        task_id = _automata_manager.add_task(
            prompt=prompt,
            interval_seconds=interval_seconds,
            end_time=end_time,
            run_immediately=run_immediately,
        )
        end_str = f", expires at {end_time}" if end_time else ", runs indefinitely"
        return (
            f"Automata job created successfully.\n"
            f"  Task ID    : {task_id}\n"
            f"  Prompt     : {prompt}\n"
            f"  Interval   : every {interval_seconds}s ({interval_seconds / 60:.1f} min){end_str}\n"
            f"Use `/automata list` in the CLI or `automata_list_jobs` to monitor it."
        )
    except Exception as exc:
        logger.error("automata_create_job failed: %s", exc, exc_info=True)
        return f"Error creating automata job: {exc}"


@tool
def automata_list_jobs() -> str:
    """List all currently scheduled automata jobs (active, stopped, and expired).

    Returns a human-readable summary table of every job, including its ID,
    prompt, interval, end time, last run time, and current status.
    Use this to check whether a recurring task already exists before creating
    a duplicate.

    Returns:
        A formatted string summary of all jobs, or a message if none exist.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    try:
        tasks = _automata_manager.list_tasks()
        if not tasks:
            return "No automata jobs are currently scheduled."

        lines = ["Automata Jobs:", ""]
        for t in tasks:
            interval_s = t.get("interval_seconds", 0)
            if interval_s >= 3600:
                interval_str = f"{interval_s / 3600:.1f}h"
            elif interval_s >= 60:
                interval_str = f"{interval_s / 60:.1f}m"
            else:
                interval_str = f"{interval_s}s"

            enabled = t.get("enabled", True)
            stale = t.get("stale", False)
            if not enabled:
                status = "EXPIRED" if t.get("last_status") == "Expired" else ("STALE" if stale else "STOPPED")
            else:
                status = t.get("last_status", "running")

            lines.append(
                f"  [{t['id']}] {t['prompt']!r}  "
                f"every {interval_str}  "
                f"end={t.get('end_time', 'never')}  "
                f"last_run={t.get('last_run', 'never')}  "
                f"status={status}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.error("automata_list_jobs failed: %s", exc, exc_info=True)
        return f"Error listing automata jobs: {exc}"


@tool
def automata_stop_job(task_id: str) -> str:
    """Stop (pause) a running automata job without permanently removing it.

    The job can be resumed later via the CLI (`/automata resume <id>`)
    or will be visible in `automata_list_jobs` with STOPPED status.

    Args:
        task_id: The 8-character task ID returned by `automata_create_job`
                 or shown in `automata_list_jobs`.

    Returns:
        Confirmation string or error message.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    try:
        success = _automata_manager.stop_task(task_id)
        if success:
            return f"Automata job '{task_id}' has been stopped. Use `/automata resume {task_id}` to restart it."
        return f"Error: No automata job found with ID '{task_id}'."
    except Exception as exc:
        logger.error("automata_stop_job failed: %s", exc, exc_info=True)
        return f"Error stopping automata job: {exc}"


@tool
def automata_get_job_logs(task_id: str) -> str:
    """List all execution log files recorded for a given automata job.

    Each time an automata job runs, the agent's output is saved as a timestamped
    Markdown log file. Use this tool to discover which log files exist for a job
    before reading one with `automata_read_job_log`.

    This mirrors the CLI command: /automata logs <job-id>

    Args:
        task_id: The 8-character task ID shown in `automata_list_jobs`.

    Returns:
        A formatted list of log filenames with their sizes, newest first.
        Use the filename with `automata_read_job_log` to read its contents.
        Returns an informational message if no logs exist yet.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    try:
        log_files = _automata_manager.get_task_logs(task_id)
        if not log_files:
            return (
                f"No execution logs found for job '{task_id}'. "
                "The job may not have run yet, or the task ID may be incorrect. "
                "Use `automata_list_jobs` to verify the job exists."
            )

        lines = [f"Execution logs for job '{task_id}' ({len(log_files)} file(s)):"]
        for p in log_files:
            size_kb = p.stat().st_size / 1024
            lines.append(f"  {p.name}  ({size_kb:.1f} KB)")
        lines.append("\nUse `automata_read_job_log` with a filename above to read its contents.")
        return "\n".join(lines)
    except Exception as exc:
        logger.error("automata_get_job_logs failed: %s", exc, exc_info=True)
        return f"Error retrieving logs for job '{task_id}': {exc}"


@tool
def automata_read_job_log(log_filename: str) -> str:
    """Read the full content of a specific automata job execution log.

    Each execution log is a Markdown report containing the task prompt,
    execution timestamp, and the agent's output for that run. Use this
    to verify whether a job succeeded and to inspect the result.

    Workflow:
      1. Call `automata_list_jobs` to find a task_id.
      2. Call `automata_get_job_logs(task_id)` to list available log filenames.
      3. Call this tool with a filename from step 2 to read its content.

    This mirrors the CLI command: /automata view <log-filename>

    Args:
        log_filename: The exact filename returned by `automata_get_job_logs`
                      (e.g. "abc12345_20260322_180000.md").

    Returns:
        The full Markdown content of the log, or an error message if the file
        is not found or the filename is invalid.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    try:
        content = _automata_manager.read_log(log_filename)
        if content == "Log file not found.":
            return (
                f"Log file '{log_filename}' not found. "
                "Use `automata_get_job_logs(<task_id>)` to get valid filenames."
            )
        return content
    except Exception as exc:
        logger.error("automata_read_job_log failed: %s", exc, exc_info=True)
        return f"Error reading log '{log_filename}': {exc}"


@tool
def automata_remove_job(task_id: str) -> str:
    """Permanently remove an automata job (cannot be undone).

    Use `automata_stop_job` instead if you want to pause the job temporarily.

    Args:
        task_id: The 8-character task ID returned by `automata_create_job`
                 or shown in `automata_list_jobs`.

    Returns:
        Confirmation string or error message.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    try:
        success = _automata_manager.remove_task(task_id)
        if success:
            return f"Automata job '{task_id}' has been permanently removed."
        return f"Error: No automata job found with ID '{task_id}'."
    except Exception as exc:
        logger.error("automata_remove_job failed: %s", exc, exc_info=True)
        return f"Error removing automata job: {exc}"

@tool
def automata_update_job(task_id: str, interval_seconds: int) -> str:
    """Update the recurring interval of an existing automata job.

    Args:
        task_id: The 8-character task ID shown in `automata_list_jobs`.
        interval_seconds: The new repeat period in seconds (must be > 0).

    Returns:
        Confirmation string or error message if the task is not found.
    """
    if _automata_manager is None:
        return "Error: AutomataManager is not available."

    if interval_seconds <= 0:
        return f"Error: interval_seconds must be > 0, got {interval_seconds}."

    try:
        success = _automata_manager.update_task_interval(task_id, interval_seconds)
        if success:
            return f"Automata job '{task_id}' interval successfully updated to {interval_seconds} seconds."
        return f"Error: No automata job found with ID '{task_id}'."
    except Exception as exc:
        logger.error("automata_update_job failed: %s", exc, exc_info=True)
        return f"Error updating automata job: {exc}"
