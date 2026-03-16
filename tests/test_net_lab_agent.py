import pytest
from subagents.net_lab_agent import net_lab_agent

def test_net_lab_agent_structure():
    assert "name" in net_lab_agent
    assert net_lab_agent["name"] == "net_lab_agent"
    assert "description" in net_lab_agent
    assert "system_prompt" in net_lab_agent
    assert "tools" in net_lab_agent
    assert isinstance(net_lab_agent["tools"], list)
