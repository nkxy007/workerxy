import pytest
import re
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from custom_middleware.skill_pruning_middleware import (
    PruneSkillsEdit, 
    AdvancedContextMiddleware
)
import langchain.agents.middleware.context_editing as ce
from langchain.agents.middleware import ModelRequest

def test_prune_skills_edit_trigger():
    # Setup messages
    messages = [
        SystemMessage(content="System prompt"),
        HumanMessage(content="Hello"),
        AIMessage(content="[SKILL INFO] Skill 1: Ansible for Networks"),
        HumanMessage(content="How do I use it?"),
        AIMessage(content="[SKILL INFO] Skill 2: DrawIO Diagrams"),
        HumanMessage(content="Nice, thanks."),
        AIMessage(content="[SKILL INFO] Skill 3: Prisma SDWAN"),
        HumanMessage(content="Latest query")
    ]
    
    # Constant token count mock for simplicity
    def count_tokens(msgs):
        return len(msgs) * 100

    # Scenario 1: Below threshold (each message is 100, total 800)
    edit = PruneSkillsEdit(trigger_tokens=1000, keep_recent=1)
    msg_copy = messages.copy()
    edit.apply(msg_copy, count_tokens)
    assert len(msg_copy) == 8, "Should not prune if below threshold"

    # Scenario 2: Above threshold, keep recent 1
    # Trigger at 500 tokens. Messages at indices 2, 4, 6 are skill info.
    # Keep index 6 (most recent). Remove indices 2 and 4.
    edit = PruneSkillsEdit(trigger_tokens=500, keep_recent=1)
    msg_copy = messages.copy()
    edit.apply(msg_copy, count_tokens)
    assert len(msg_copy) == 6
    contents = [m.content for m in msg_copy]
    assert "[SKILL INFO] Skill 3: Prisma SDWAN" in contents
    assert "[SKILL INFO] Skill 1: Ansible for Networks" not in contents
    assert "[SKILL INFO] Skill 2: DrawIO Diagrams" not in contents
    
    # Scenario 3: Above threshold, keep recent 2
    edit = PruneSkillsEdit(trigger_tokens=500, keep_recent=2)
    msg_copy = messages.copy()
    edit.apply(msg_copy, count_tokens)
    assert len(msg_copy) == 7
    contents = [m.content for m in msg_copy]
    assert "[SKILL INFO] Skill 3: Prisma SDWAN" in contents
    assert "[SKILL INFO] Skill 2: DrawIO Diagrams" in contents
    assert "[SKILL INFO] Skill 1: Ansible for Networks" not in contents

def test_skill_pattern_matching():
    # Verify different patterns work
    edit = PruneSkillsEdit(trigger_tokens=0) # Always trigger
    
    def count_tokens(msgs): return 100
    
    msgs = [
        AIMessage(content="Loaded skill: test"),
        AIMessage(content="<skill>Another test</skill>"),
        AIMessage(content="[SKILL INFO] Final test")
    ]
    
    msgs_copy = msgs.copy()
    edit.apply(msgs_copy, count_tokens)
    assert len(msgs_copy) == 1
    assert "Final test" in msgs_copy[0].content

@pytest.mark.asyncio
async def test_advanced_context_middleware_initialization():
    # Verify that the middleware initializes its inner components correctly
    max_tokens = 200000
    middleware = AdvancedContextMiddleware(
        max_tokens=max_tokens, 
        trigger_ratio=0.85,
        summarize_model=None # Explicitly None for test
    )
    
    assert middleware.max_tokens == 200000
    assert middleware.trigger_tokens == 170000
    assert len(middleware.context_editor.edits) == 2
    assert isinstance(middleware.context_editor.edits[0], PruneSkillsEdit)
    assert middleware.context_editor.edits[0].trigger_tokens == 170000

@pytest.mark.asyncio
async def test_advanced_context_middleware_trigger_logic(monkeypatch):
    # Mock token counter to return a high value
    monkeypatch.setattr(ce, "count_tokens_approximately", lambda msgs: 1000)
    
    middleware = AdvancedContextMiddleware(
        max_tokens=1000, 
        trigger_ratio=0.5, # trigger at 500
        token_count_method="approximate",
        summarize_model=None # Explicitly None for test
    )
    
    # Sample messages with skill info
    messages = [
        AIMessage(content="[SKILL INFO] old"),
        AIMessage(content="[SKILL INFO] new"),
        HumanMessage(content="test")
    ]
    
    request = ModelRequest(messages=messages, model=MagicMock())
    
    # Handler to capture the request
    captured_request = None
    async def handler(req):
        nonlocal captured_request
        captured_request = req
        return AIMessage(content="ok")

    # Call the middleware
    await middleware.awrap_model_call(request, handler)
    
    # Check if messages were pruned (should have kept only "new")
    assert captured_request is not None
    pruned_msgs = captured_request.messages
    # Index 0 was "old", Index 1 was "new". Pruned index 0.
    assert len(pruned_msgs) == 2
    assert "[SKILL INFO] old" not in [m.content for m in pruned_msgs]
    assert "[SKILL INFO] new" in [m.content for m in pruned_msgs]

