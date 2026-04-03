"""
test_automata_tools.py
----------------------
Unit tests for tools_helpers/automata_tools.py

Does NOT require a live MCP server or agent.
All AutomataManager calls are mocked.

Run with:
    conda run -n test_langchain_env python -m pytest tests/test_automata_tools.py -v
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path so imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_manager(task_list=None):
    """Return a mock AutomataManager with sensible defaults."""
    mgr = MagicMock()
    mgr.add_task.return_value = "abc12345"
    mgr.stop_task.return_value = True
    mgr.remove_task.return_value = True
    mgr.list_tasks.return_value = task_list or []
    return mgr


def _reset_module_manager():
    """Reset the module-level manager to None between tests."""
    import tools_helpers.automata_tools as at
    at._automata_manager = None


# ---------------------------------------------------------------------------
# Test 1: set_automata_manager stores the reference
# ---------------------------------------------------------------------------

def test_set_and_get_manager():
    _reset_module_manager()
    import tools_helpers.automata_tools as at

    mgr = _make_mock_manager()
    at.set_automata_manager(mgr)
    assert at._automata_manager is mgr, "Manager reference should be stored in module"
    print("[PASS] test_set_and_get_manager")


# ---------------------------------------------------------------------------
# Test 2: create_job returns error string when no manager is set
# ---------------------------------------------------------------------------

def test_create_job_no_manager():
    _reset_module_manager()
    from tools_helpers.automata_tools import automata_create_job

    result = automata_create_job.invoke({
        "prompt": "ping 8.8.8.8",
        "interval_seconds": 3600,
        "end_time": None,
    })
    assert "Error" in result, f"Expected error string, got: {result}"
    assert "AutomataManager" in result
    print(f"[PASS] test_create_job_no_manager  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 3: create_job with interval_seconds <= 0 returns error
# ---------------------------------------------------------------------------

def test_create_job_invalid_interval():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    at._automata_manager = _make_mock_manager()
    from tools_helpers.automata_tools import automata_create_job

    result = automata_create_job.invoke({
        "prompt": "ping 8.8.8.8",
        "interval_seconds": 0,
        "end_time": None,
    })
    assert "Error" in result
    assert "interval_seconds" in result
    print(f"[PASS] test_create_job_invalid_interval  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 4: create_job success — add_task called with correct args
# ---------------------------------------------------------------------------

def test_create_job_success():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_create_job

    result = automata_create_job.invoke({
        "prompt": "ping 8.8.8.8 and report latency",
        "interval_seconds": 3600,
        "end_time": "2026-03-22T23:00:00",
    })

    mgr.add_task.assert_called_once_with(
        prompt="ping 8.8.8.8 and report latency",
        interval_seconds=3600,
        end_time="2026-03-22T23:00:00",
        run_immediately=True,
    )
    assert "abc12345" in result, f"Task ID should appear in result: {result}"
    assert "3600" in result
    print(f"[PASS] test_create_job_success  →  '{result[:80]}...'")


# ---------------------------------------------------------------------------
# Test 5: create_job success without end_time
# ---------------------------------------------------------------------------

def test_create_job_no_end_time():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_create_job

    result = automata_create_job.invoke({
        "prompt": "check syslog",
        "interval_seconds": 900,
        "end_time": None,
    })

    mgr.add_task.assert_called_once_with(prompt="check syslog", interval_seconds=900, end_time=None, run_immediately=True)
    assert "abc12345" in result
    assert "indefinitely" in result
    print(f"[PASS] test_create_job_no_end_time  →  '{result[:80]}...'")


# ---------------------------------------------------------------------------
# Test 6: list_jobs with no tasks
# ---------------------------------------------------------------------------

def test_list_jobs_empty():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    at._automata_manager = _make_mock_manager(task_list=[])

    from tools_helpers.automata_tools import automata_list_jobs
    result = automata_list_jobs.invoke({})

    assert "No automata jobs" in result, f"Unexpected result: {result}"
    print(f"[PASS] test_list_jobs_empty  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 7: list_jobs with tasks
# ---------------------------------------------------------------------------

def test_list_jobs_populated():
    _reset_module_manager()
    import tools_helpers.automata_tools as at

    tasks = [
        {
            "id": "abc12345",
            "prompt": "ping 8.8.8.8",
            "interval_seconds": 3600,
            "end_time": "2026-03-22T23:00:00",
            "last_run": "never",
            "enabled": True,
            "last_status": "success",
        },
        {
            "id": "def67890",
            "prompt": "check syslog",
            "interval_seconds": 600,
            "end_time": None,
            "last_run": "2026-03-22T20:00:00",
            "enabled": False,
            "stale": False,
            "last_status": "Stopped",
        },
    ]
    at._automata_manager = _make_mock_manager(task_list=tasks)

    from tools_helpers.automata_tools import automata_list_jobs
    result = automata_list_jobs.invoke({})

    assert "abc12345" in result
    assert "def67890" in result
    assert "ping 8.8.8.8" in result
    print(f"[PASS] test_list_jobs_populated  →  {len(result)} chars")


# ---------------------------------------------------------------------------
# Test 8: list_jobs with no manager
# ---------------------------------------------------------------------------

def test_list_jobs_no_manager():
    _reset_module_manager()
    from tools_helpers.automata_tools import automata_list_jobs
    result = automata_list_jobs.invoke({})
    assert "Error" in result
    print(f"[PASS] test_list_jobs_no_manager  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 9: stop_job success
# ---------------------------------------------------------------------------

def test_stop_job_success():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_stop_job
    result = automata_stop_job.invoke({"task_id": "abc12345"})

    mgr.stop_task.assert_called_once_with("abc12345")
    assert "stopped" in result.lower()
    assert "abc12345" in result
    print(f"[PASS] test_stop_job_success  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 10: stop_job not found
# ---------------------------------------------------------------------------

def test_stop_job_not_found():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.stop_task.return_value = False
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_stop_job
    result = automata_stop_job.invoke({"task_id": "xxxxxxxx"})

    assert "not found" in result.lower() or "Error" in result
    print(f"[PASS] test_stop_job_not_found  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 11: remove_job success
# ---------------------------------------------------------------------------

def test_remove_job_success():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_remove_job
    result = automata_remove_job.invoke({"task_id": "abc12345"})

    mgr.remove_task.assert_called_once_with("abc12345")
    assert "removed" in result.lower()
    assert "abc12345" in result
    print(f"[PASS] test_remove_job_success  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 12: remove_job not found
# ---------------------------------------------------------------------------

def test_remove_job_not_found():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.remove_task.return_value = False
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_remove_job
    result = automata_remove_job.invoke({"task_id": "xxxxxxxx"})

    assert "not found" in result.lower() or "Error" in result
    print(f"[PASS] test_remove_job_not_found  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 13: get_job_logs — no manager
# ---------------------------------------------------------------------------

def test_get_job_logs_no_manager():
    _reset_module_manager()
    from tools_helpers.automata_tools import automata_get_job_logs
    result = automata_get_job_logs.invoke({"task_id": "abc12345"})
    assert "Error" in result
    print(f"[PASS] test_get_job_logs_no_manager  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 14: get_job_logs — no logs yet
# ---------------------------------------------------------------------------

def test_get_job_logs_empty():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.get_task_logs.return_value = []
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_get_job_logs
    result = automata_get_job_logs.invoke({"task_id": "abc12345"})

    assert "No execution logs" in result
    assert "abc12345" in result
    print(f"[PASS] test_get_job_logs_empty  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 15: get_job_logs — returns filenames
# ---------------------------------------------------------------------------

def test_get_job_logs_with_files():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    from unittest.mock import MagicMock

    # Create mock Path objects
    mock_path_1 = MagicMock()
    mock_path_1.name = "abc12345_20260323_060000.md"
    mock_path_1.stat.return_value.st_size = 1024

    mock_path_2 = MagicMock()
    mock_path_2.name = "abc12345_20260323_050000.md"
    mock_path_2.stat.return_value.st_size = 512

    mgr = _make_mock_manager()
    mgr.get_task_logs.return_value = [mock_path_1, mock_path_2]
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_get_job_logs
    result = automata_get_job_logs.invoke({"task_id": "abc12345"})

    assert "abc12345_20260323_060000.md" in result
    assert "abc12345_20260323_050000.md" in result
    assert "2 file(s)" in result
    assert "automata_read_job_log" in result  # usage hint is present
    print(f"[PASS] test_get_job_logs_with_files  →  {len(result)} chars")


# ---------------------------------------------------------------------------
# Test 16: read_job_log — success
# ---------------------------------------------------------------------------

def test_read_job_log_success():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    log_content = (
        "# Automata Execution Report\n"
        "**Task ID:** abc12345\n"
        "**Prompt:** ping 8.8.8.8 and report latency\n\n"
        "## Result\n\nPing successful. RTT: 12ms\n"
    )
    mgr.read_log.return_value = log_content
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_read_job_log
    result = automata_read_job_log.invoke({"log_filename": "abc12345_20260323_060000.md"})

    mgr.read_log.assert_called_once_with("abc12345_20260323_060000.md")
    assert "RTT: 12ms" in result
    assert "abc12345" in result
    print(f"[PASS] test_read_job_log_success  →  {len(result)} chars")


# ---------------------------------------------------------------------------
# Test 17: read_job_log — file not found
# ---------------------------------------------------------------------------

def test_read_job_log_not_found():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.read_log.return_value = "Log file not found."
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_read_job_log
    result = automata_read_job_log.invoke({"log_filename": "nonexistent.md"})

    assert "not found" in result.lower()
    assert "automata_get_job_logs" in result  # guidance to use correct tool
    print(f"[PASS] test_read_job_log_not_found  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 18: update_job — success
# ---------------------------------------------------------------------------

def test_update_job_success():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.update_task_interval.return_value = True
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_update_job
    result = automata_update_job.invoke({"task_id": "abc12345", "interval_seconds": 3600})

    mgr.update_task_interval.assert_called_once_with("abc12345", 3600)
    assert "successfully updated" in result
    print(f"[PASS] test_update_job_success  →  '{result}'")


# ---------------------------------------------------------------------------
# Test 19: update_job — not found
# ---------------------------------------------------------------------------

def test_update_job_not_found():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    mgr.update_task_interval.return_value = False
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_update_job
    result = automata_update_job.invoke({"task_id": "xxxxxxxx", "interval_seconds": 3600})

    assert "not found" in result.lower() or "Error" in result
    print(f"[PASS] test_update_job_not_found  →  '{result}'")

# ---------------------------------------------------------------------------
# Test 20: update_job — invalid interval
# ---------------------------------------------------------------------------

def test_update_job_invalid_interval():
    _reset_module_manager()
    import tools_helpers.automata_tools as at
    mgr = _make_mock_manager()
    at._automata_manager = mgr

    from tools_helpers.automata_tools import automata_update_job
    result = automata_update_job.invoke({"task_id": "abc12345", "interval_seconds": 0})

    assert "Error" in result
    assert "interval_seconds must be > 0" in result
    print(f"[PASS] test_update_job_invalid_interval  →  '{result}'")


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_set_and_get_manager()
    test_create_job_no_manager()
    test_create_job_invalid_interval()
    test_create_job_success()
    test_create_job_no_end_time()
    test_list_jobs_empty()
    test_list_jobs_populated()
    test_list_jobs_no_manager()
    test_stop_job_success()
    test_stop_job_not_found()
    test_remove_job_success()
    test_remove_job_not_found()
    test_get_job_logs_no_manager()
    test_get_job_logs_empty()
    test_get_job_logs_with_files()
    test_read_job_log_success()
    test_read_job_log_not_found()
    test_update_job_success()
    test_update_job_not_found()
    test_update_job_invalid_interval()
    print("\n✅ All automata_tools tests passed!")
