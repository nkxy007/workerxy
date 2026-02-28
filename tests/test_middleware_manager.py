import json
import pytest
from pathlib import Path
from net_deepagent_cli.middleware_manager import MiddlewareManager

@pytest.fixture
def temp_manager(tmp_path, monkeypatch):
    """Fixture to create a MiddlewareManager with a temporary config directory."""
    agent_name = "test-agent"
    
    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    
    manager = MiddlewareManager(agent_name)
    return manager

def test_middleware_manager_initialization(temp_manager):
    """Test that manager initializes with default values."""
    all_mw = temp_manager.list_all()
    assert "advanced_context" in all_mw
    assert "netpii" in all_mw
    assert all_mw["advanced_context"]["enabled"] is True
    assert all_mw["netpii"]["enabled"] is False

def test_toggle_middleware(temp_manager):
    """Test toggling middleware state."""
    # Enable netpii
    success = temp_manager.toggle_middleware("netpii", True)
    assert success is True
    assert temp_manager.available_middlewares["netpii"]["enabled"] is True
    
    # Verify persistence
    reloaded = MiddlewareManager(temp_manager.agent_name)
    assert reloaded.available_middlewares["netpii"]["enabled"] is True

def test_update_middleware_params(temp_manager):
    """Test updating and persisting parameters."""
    new_params = {"pii_types": ["ip", "email"]}
    success = temp_manager.update_middleware_params("netpii", new_params)
    
    assert success is True
    assert temp_manager.available_middlewares["netpii"]["params"]["pii_types"] == ["ip", "email"]
    
    # Verify persistence
    reloaded = MiddlewareManager(temp_manager.agent_name)
    assert reloaded.available_middlewares["netpii"]["params"]["pii_types"] == ["ip", "email"]

def test_update_context_params(temp_manager):
    """Test updating complex parameters."""
    new_params = {
        "trigger_ratio": 0.5,
        "keep_skills": 5
    }
    temp_manager.update_middleware_params("advanced_context", new_params)
    
    reloaded = MiddlewareManager(temp_manager.agent_name)
    params = reloaded.available_middlewares["advanced_context"]["params"]
    assert params["trigger_ratio"] == 0.5
    assert params["keep_skills"] == 5
    # Ensure other params are preserved (partial update)
    assert "max_tokens" in params

def test_get_enabled_middlewares(temp_manager):
    """Test retrieving enabled middleware configs."""
    temp_manager.toggle_middleware("advanced_context", True)
    temp_manager.toggle_middleware("netpii", True)
    
    enabled = temp_manager.get_enabled_middlewares()
    assert len(enabled) == 2
    names = [e["name"] for e in enabled]
    assert "Advanced Context Pruning" in names
    assert "NetPII Pseudonymization" in names
