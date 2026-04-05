"""
tests/test_third_party_subagent_loader.py
------------------------------------------
Unit tests for utils/third_party_subagent_loader.py.

Run with:
    conda run -n test_langchain_env pytest tests/test_third_party_subagent_loader.py -v

All tests are self-contained – no network calls, no MCP server required.
MCP tools and LLM models are replaced with lightweight MagicMock objects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on the path so 'utils' is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Stub out heavy imports BEFORE importing the module under test.
# The loader does:  ``from net_deepagent import filter_tools_by_category``
# only inside _resolve_tools(), so we can monkeypatch via sys.modules.
# ---------------------------------------------------------------------------

_fake_net_deepagent = MagicMock()
_fake_net_deepagent.filter_tools_by_category = lambda tools, cat: [
    t for t in tools if t.name.startswith(cat + "_")
]
sys.modules.setdefault("net_deepagent", _fake_net_deepagent)

# Also stub every other heavy dep the project pulls on import
for _mod in [
    "langchain_core", "langchain_core.tools", "langchain_core.messages",
    "langchain", "langchain.agents", "langchain.agents.middleware",
    "langgraph", "langgraph.graph", "langgraph.checkpoint",
    "langgraph.checkpoint.memory", "langgraph.store", "langgraph.store.memory",
    "langgraph.runtime",
    "deepagents", "deepagents.backends",
    "langchain_mcp_adapters", "langchain_mcp_adapters.client",
    "utils.credentials_helper", "utils.llm_provider",
    "net_deepagent_cli", "net_deepagent_cli.communication",
    "net_deepagent_cli.communication.logger",
    "net_deepagent_cli.communication.notifications",
    "custom_middleware", "custom_middleware.netpii_middlewares",
    "custom_middleware.tool_announcer_middleware",
    "prompts", "browser_use", "pydantic",
]:
    sys.modules.setdefault(_mod, MagicMock())

from utils.third_party_subagent_loader import (  # noqa: E402
    get_third_party_subagents_dir,
    load_third_party_subagents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


def _make_tools(*names: str) -> list:
    return [_make_tool(n) for n in names]


def _make_models(*keys: str) -> dict:
    return {k: MagicMock(name=k) for k in keys}


def _write_agent(subagents_dir: Path, agent_name: str, spec: dict) -> Path:
    agent_dir = subagents_dir / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.json").write_text(json.dumps(spec), encoding="utf-8")
    return agent_dir


def _base_spec(**overrides) -> dict:
    spec = {
        "name": "test_agent",
        "description": "A test agent.",
        "system_prompt": "You are a test agent.",
    }
    spec.update(overrides)
    return spec


def _run(subagents_dir, all_mcp_tools=None, available_models=None, builtin_tools=None):
    """Helper that patches get_third_party_subagents_dir and calls the loader."""
    with patch(
        "utils.third_party_subagent_loader.get_third_party_subagents_dir",
        return_value=subagents_dir,
    ):
        return load_third_party_subagents(
            all_mcp_tools=all_mcp_tools or [],
            available_models=available_models or _make_models("gpt-5-mini"),
            builtin_tools=builtin_tools or {},
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_loads_valid_agent(self, tmp_path):
        """A complete, valid agent.json must be parsed and returned."""
        d = tmp_path / "subagents"
        d.mkdir()
        _write_agent(d, "my_agent", _base_spec())
        result = _run(d)
        assert len(result) == 1
        a = result[0]
        assert a["name"] == "test_agent"
        assert a["description"] == "A test agent."
        assert a["system_prompt"] == "You are a test agent."

    def test_multiple_agents_loaded(self, tmp_path):
        """Multiple valid agent folders must all be loaded."""
        d = tmp_path / "subagents"
        d.mkdir()
        for i in range(3):
            _write_agent(d, f"agent_{i}", _base_spec(name=f"agent_{i}"))
        result = _run(d)
        assert len(result) == 3
        assert {a["name"] for a in result} == {"agent_0", "agent_1", "agent_2"}


class TestEnabledFlag:
    def test_disabled_agent_skipped(self, tmp_path):
        """``enabled: false`` must cause the agent to be skipped."""
        d = tmp_path / "subagents"
        d.mkdir()
        _write_agent(d, "off_agent", _base_spec(enabled=False))
        assert _run(d) == []


class TestValidation:
    @pytest.mark.parametrize("missing_field", ["name", "description", "system_prompt"])
    def test_missing_required_field_skipped(self, tmp_path, missing_field):
        """An agent missing any required field must be silently skipped."""
        d = tmp_path / "subagents"
        d.mkdir()
        spec = _base_spec()
        del spec[missing_field]
        _write_agent(d, "bad_agent", spec)
        assert _run(d) == []

    def test_invalid_json_skipped(self, tmp_path):
        """Malformed JSON must not crash the loader — agent is skipped."""
        d = tmp_path / "subagents"
        d.mkdir()
        agent_dir = d / "broken_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.json").write_text("{ not valid json !!!", encoding="utf-8")
        assert _run(d) == []

    def test_directory_not_exist(self, tmp_path):
        """If the subagents directory doesn't exist, return an empty list."""
        non_existent = tmp_path / "does_not_exist"
        with patch(
            "utils.third_party_subagent_loader.get_third_party_subagents_dir",
            return_value=non_existent,
        ):
            result = load_third_party_subagents(
                all_mcp_tools=[], available_models={}, builtin_tools={}
            )
        assert result == []


class TestToolResolution:
    def test_tool_filter_prefixes(self, tmp_path):
        """Tools matching a declared prefix must be added."""
        d = tmp_path / "subagents"
        d.mkdir()
        tools = _make_tools("snow_incident", "snow_change", "jira_ticket", "net_ping")
        _write_agent(d, "snow_agent", _base_spec(tool_filter={"prefixes": ["snow_"]}))
        result = _run(d, all_mcp_tools=tools)
        assert len(result) == 1
        resolved = {t.name for t in result[0]["tools"]}
        assert resolved == {"snow_incident", "snow_change"}

    def test_tool_filter_names(self, tmp_path):
        """Exact tool names in ``tool_filter.names`` must be resolved."""
        d = tmp_path / "subagents"
        d.mkdir()
        tools = _make_tools("alpha", "beta", "gamma")
        _write_agent(d, "named_agent", _base_spec(tool_filter={"names": ["beta"]}))
        result = _run(d, all_mcp_tools=tools)
        assert {t.name for t in result[0]["tools"]} == {"beta"}

    def test_tool_filter_categories(self, tmp_path):
        """Category-based filtering must use filter_tools_by_category."""
        d = tmp_path / "subagents"
        d.mkdir()
        # The stubbed filter_tools_by_category matches "<cat>_" prefix
        tools = _make_tools("servicenow_incident", "servicenow_change", "other_tool")
        _write_agent(d, "cat_agent", _base_spec(tool_filter={"categories": ["servicenow"]}))
        result = _run(d, all_mcp_tools=tools)
        assert {t.name for t in result[0]["tools"]} == {
            "servicenow_incident", "servicenow_change"
        }

    def test_include_builtin_tools(self, tmp_path):
        """``include_tools`` must resolve named built-in tool objects."""
        d = tmp_path / "subagents"
        d.mkdir()
        search_tool = _make_tool("search_internet")
        clarify_tool = _make_tool("user_clarification_and_action_tool")
        builtin_map = {
            "search_internet": search_tool,
            "user_clarification_and_action_tool": clarify_tool,
        }
        _write_agent(d, "builtin_agent", _base_spec(include_tools=["search_internet"]))
        result = _run(d, builtin_tools=builtin_map)
        assert search_tool in result[0]["tools"]
        assert clarify_tool not in result[0]["tools"]


class TestSkillsResolution:
    def test_skills_resolved(self, tmp_path):
        """Valid skill paths (containing SKILL.md) must appear in agent dict."""
        d = tmp_path / "subagents"
        d.mkdir()
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")

        _write_agent(d, "skilled_agent", _base_spec(skills=[str(skill_dir)]))
        result = _run(d)
        assert "skills" in result[0]
        assert any(str(skill_dir) in s for s in result[0]["skills"])

    def test_skills_invalid_path_skipped(self, tmp_path):
        """A skill path with no SKILL.md must be omitted; agent still loads."""
        d = tmp_path / "subagents"
        d.mkdir()
        bad_skill = tmp_path / "no_skill_md"
        bad_skill.mkdir()  # exists but contains no SKILL.md

        _write_agent(d, "bad_skill_agent", _base_spec(skills=[str(bad_skill)]))
        result = _run(d)
        assert len(result) == 1
        assert result[0].get("skills", []) == []


class TestModelResolution:
    def test_model_resolution(self, tmp_path):
        """The ``model`` key must map to the correct object."""
        d = tmp_path / "subagents"
        d.mkdir()
        models = _make_models("gpt-5-mini", "gpt-5.1")
        _write_agent(d, "big_agent", _base_spec(model="gpt-5.1"))
        result = _run(d, available_models=models)
        assert result[0]["model"] is models["gpt-5.1"]

    def test_model_defaults_to_fallback(self, tmp_path):
        """When ``model`` is omitted the loader uses the default key."""
        d = tmp_path / "subagents"
        d.mkdir()
        models = _make_models("gpt-5-mini")
        _write_agent(d, "default_agent", _base_spec())  # no model key
        result = _run(d, available_models=models)
        assert result[0]["model"] is models["gpt-5-mini"]

    def test_model_unknown_key_falls_back(self, tmp_path):
        """An unrecognised model key must fall back gracefully."""
        d = tmp_path / "subagents"
        d.mkdir()
        models = _make_models("gpt-5-mini")
        _write_agent(d, "weird_model_agent", _base_spec(model="unknown-model-xyz"))
        result = _run(d, available_models=models)
        assert len(result) == 1
        assert result[0]["model"] is models["gpt-5-mini"]
