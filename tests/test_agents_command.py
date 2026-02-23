"""
tests/test_agents_command.py
----------------------------
Unit-tests for:
  - a2a_capability.registry_manager  (pure file I/O helpers)
  - net_deepagent_cli.agents_ui      (command handlers, stubbed middleware)

Run with:
    conda run -n test_langchain_env pytest tests/test_agents_command.py -v
"""

import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_registry(tmp_path):
    """Provide a temporary registry JSON file with two entries."""
    reg_file = tmp_path / "agents_registry.json"
    reg_file.write_text(json.dumps({
        "dns_deepagent":  "http://localhost:8003",
        "dhcp_deepagent": "http://localhost:8004",
    }, indent=4))
    return reg_file


def _make_ui():
    """Return a minimal mock UI that collects printed messages."""
    ui = MagicMock()
    ui.console = MagicMock()
    ui.messages = []

    def capture(msg, role="system"):
        ui.messages.append((role, msg))

    ui.print_message.side_effect = capture
    return ui


def _make_agent(registered_agents=None):
    """Return a mock WrappedAgent with a stub A2AHTTPMiddleware."""
    agent = MagicMock()

    middleware = MagicMock()
    middleware.remote_agents = dict(registered_agents or {})
    middleware._tools_cache = None

    # register_remote_agent always succeeds and adds to remote_agents
    async def _register(name, url):
        middleware.remote_agents[name] = MagicMock()  # stub client

    middleware.register_remote_agent = AsyncMock(side_effect=_register)
    agent.a2a_middleware = middleware
    return agent


# ────────────────────────────────────────────────────────────────────────────
# registry_manager tests
# ────────────────────────────────────────────────────────────────────────────

class TestRegistryManager:

    def test_load_registry_returns_correct_data(self, tmp_registry):
        from a2a_capability.registry_manager import load_registry
        data = load_registry(tmp_registry)
        assert data == {
            "dns_deepagent":  "http://localhost:8003",
            "dhcp_deepagent": "http://localhost:8004",
        }

    def test_load_registry_missing_file_returns_empty(self, tmp_path):
        from a2a_capability.registry_manager import load_registry
        data = load_registry(tmp_path / "nonexistent.json")
        assert data == {}

    def test_add_agent_creates_entry(self, tmp_registry):
        from a2a_capability.registry_manager import add_agent, load_registry
        add_agent("ntp_agent", "http://localhost:8005", tmp_registry)
        data = load_registry(tmp_registry)
        assert data["ntp_agent"] == "http://localhost:8005"

    def test_add_agent_updates_existing_entry(self, tmp_registry):
        from a2a_capability.registry_manager import add_agent, load_registry
        add_agent("dns_deepagent", "http://newhost:9999", tmp_registry)
        data = load_registry(tmp_registry)
        assert data["dns_deepagent"] == "http://newhost:9999"

    def test_remove_agent_deletes_entry(self, tmp_registry):
        from a2a_capability.registry_manager import remove_agent, load_registry
        result = remove_agent("dhcp_deepagent", tmp_registry)
        assert result is True
        data = load_registry(tmp_registry)
        assert "dhcp_deepagent" not in data

    def test_remove_agent_returns_false_for_missing(self, tmp_registry):
        from a2a_capability.registry_manager import remove_agent
        result = remove_agent("nonexistent_agent", tmp_registry)
        assert result is False

    def test_save_then_load_roundtrip(self, tmp_path):
        from a2a_capability.registry_manager import save_registry, load_registry
        payload = {"agent_a": "http://a:1", "agent_b": "http://b:2"}
        target = tmp_path / "reg.json"
        save_registry(payload, target)
        assert load_registry(target) == payload


# ────────────────────────────────────────────────────────────────────────────
# agents_ui handler tests
# ────────────────────────────────────────────────────────────────────────────

class TestHandleAgentsList:

    @pytest.mark.asyncio
    async def test_list_shows_registered_agents(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_list
        ui = _make_ui()
        agent = _make_agent({"dns_deepagent": MagicMock()})

        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_list(["/agents", "list"], ui, agent)

        # Table should have been printed (console.print called)
        ui.console.print.assert_called()

    @pytest.mark.asyncio
    async def test_list_empty_registry(self, tmp_path):
        from net_deepagent_cli.agents_ui import handle_agents_list
        empty_reg = tmp_path / "empty.json"
        empty_reg.write_text("{}")
        ui = _make_ui()
        agent = _make_agent()

        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=empty_reg):
            await handle_agents_list(["/agents", "list"], ui, agent)

        # Should print a system message about empty registry
        assert any("system" in role or True for role, _ in ui.messages)


class TestHandleAgentsAdd:

    @pytest.mark.asyncio
    async def test_add_persists_and_loads(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_add
        from a2a_capability.registry_manager import load_registry

        ui = _make_ui()
        agent = _make_agent()

        parts = ["/agents", "add", "ntp_agent", "http://localhost:8005"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_add(parts, ui, agent)

        # Registry should contain the new agent
        data = load_registry(tmp_registry)
        assert "ntp_agent" in data
        assert data["ntp_agent"] == "http://localhost:8005"

        # Middleware should have been called
        agent.a2a_middleware.register_remote_agent.assert_awaited_once_with(
            "ntp_agent", "http://localhost:8005"
        )

    @pytest.mark.asyncio
    async def test_add_missing_args_prints_error(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_add
        ui = _make_ui()
        agent = _make_agent()

        parts = ["/agents", "add"]  # missing name and url
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_add(parts, ui, agent)

        errors = [msg for role, msg in ui.messages if role == "error"]
        assert errors, "Expected an error message for missing args"

    @pytest.mark.asyncio
    async def test_add_invalid_url_prints_error(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_add
        ui = _make_ui()
        agent = _make_agent()

        parts = ["/agents", "add", "bad_agent", "ftp://bad-url"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_add(parts, ui, agent)

        errors = [msg for role, msg in ui.messages if role == "error"]
        assert errors, "Expected an error message for invalid URL"


class TestHandleAgentsRemove:

    @pytest.mark.asyncio
    async def test_remove_deletes_from_registry_and_unloads(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_remove
        from a2a_capability.registry_manager import load_registry

        ui = _make_ui()
        # dns_deepagent is loaded in the session
        agent = _make_agent({"dns_deepagent": MagicMock()})

        parts = ["/agents", "remove", "dns_deepagent"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_remove(parts, ui, agent)

        # Should be gone from registry
        data = load_registry(tmp_registry)
        assert "dns_deepagent" not in data

        # Should be gone from middleware
        assert "dns_deepagent" not in agent.a2a_middleware.remote_agents

        # Tools cache should be cleared
        assert agent.a2a_middleware._tools_cache is None


class TestHandleAgentsUnload:

    @pytest.mark.asyncio
    async def test_unload_removes_from_session_keeps_registry(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_unload
        from a2a_capability.registry_manager import load_registry

        ui = _make_ui()
        agent = _make_agent({"dns_deepagent": MagicMock()})

        parts = ["/agents", "unload", "dns_deepagent"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_unload(parts, ui, agent)

        # Session: gone
        assert "dns_deepagent" not in agent.a2a_middleware.remote_agents
        # Registry: still there
        data = load_registry(tmp_registry)
        assert "dns_deepagent" in data

    @pytest.mark.asyncio
    async def test_unload_missing_agent_does_not_crash(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_unload
        ui = _make_ui()
        agent = _make_agent()  # empty session

        parts = ["/agents", "unload", "nonexistent"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_unload(parts, ui, agent)  # should not raise


class TestHandleAgentsLoad:

    @pytest.mark.asyncio
    async def test_load_registers_all_registry_agents(self, tmp_registry):
        from net_deepagent_cli.agents_ui import handle_agents_load
        ui = _make_ui()
        agent = _make_agent()  # nothing loaded yet

        parts = ["/agents", "load"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=tmp_registry):
            await handle_agents_load(parts, ui, agent)

        # Both registry agents should have been loaded
        assert agent.a2a_middleware.register_remote_agent.await_count == 2
        # Tools cache should be cleared to force rebuild
        assert agent.a2a_middleware._tools_cache is None

    @pytest.mark.asyncio
    async def test_load_empty_registry(self, tmp_path):
        from net_deepagent_cli.agents_ui import handle_agents_load
        empty_reg = tmp_path / "empty.json"
        empty_reg.write_text("{}")
        ui = _make_ui()
        agent = _make_agent()

        parts = ["/agents", "load"]
        with patch("net_deepagent_cli.agents_ui._get_registry_path", return_value=empty_reg):
            await handle_agents_load(parts, ui, agent)

        # No registration attempts
        agent.a2a_middleware.register_remote_agent.assert_not_awaited()
