import pytest
from subagents.service_desk_agent import service_desk_agent

def test_service_desk_agent_structure():
    assert "name" in service_desk_agent
    assert service_desk_agent["name"] == "service_desk_agent"
    assert "description" in service_desk_agent
    assert "system_prompt" in service_desk_agent
    assert "tools" in service_desk_agent
    assert isinstance(service_desk_agent["tools"], list)
