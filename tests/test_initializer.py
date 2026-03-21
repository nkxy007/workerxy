import json
import pytest
from unittest.mock import patch
import importlib

import initializer

def test_gather_features(monkeypatch):
    inputs = iter(['y', 'n', 'y'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    features = initializer.gather_features()
    assert features["mcp"] is True
    assert features["headless"] is True
    assert features["discord"] is False
    assert features["webui"] is True

def test_gather_credentials_new_file(monkeypatch, tmp_path):
    creds_file = tmp_path / "creds.json"
    monkeypatch.setattr(initializer, 'CREDS_FILE', creds_file)
    
    inputs = iter(['test_openai_key', 'test_anthropic_key'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    initializer.gather_credentials()
    
    with open(creds_file, 'r') as f:
        data = json.load(f)
        assert data["OPENAI_API_KEY"] == "test_openai_key"
        assert data["ANTHROPIC_API_KEY"] == "test_anthropic_key"

def test_set_preferences_new_file(monkeypatch, tmp_path):
    prefs_file = tmp_path / "preferences.json"
    monkeypatch.setattr(initializer, 'PREFS_FILE', prefs_file)
    
    inputs = iter(['2', '123456789'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    initializer.set_preferences()
    
    with open(prefs_file, 'r') as f:
        data = json.load(f)
        assert data["default_model"] == "claude-3-7-sonnet-20250219"
        assert data["discord_channel"] == "123456789"
