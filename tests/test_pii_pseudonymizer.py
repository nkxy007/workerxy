import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from custom_middleware.netpii_middlewares import (
    pseudonymize_text,
    depseudonymize_text,
    PIIPseudonymizationMiddleware
)

def test_pseudonymize_basic():
    text = "Contact alice@example.com at 192.168.1.1"
    masked, mapping = pseudonymize_text(text, pii_types=["email", "ip"])
    assert "alice@example.com" not in masked
    assert "192.168.1.1" not in masked
    assert "<<pii:email:1>>" in masked
    assert "<<pii:ip:1>>" in masked
    
    # Test reversibility
    decoded = depseudonymize_text(masked, mapping)
    assert decoded == text

def test_middleware_pii_masking_before_model():
    mw = PIIPseudonymizationMiddleware(apply_to_input=True, apply_to_tool_results=True)
    
    # 1. Test HumanMessage
    state = {"messages": [HumanMessage(content="My email is bob@work.com")]}
    updates = mw.before_model(state, None)
    assert updates is not None
    assert "bob@work.com" not in updates["messages"][0].content
    assert "<<pii:email:1>>" in updates["messages"][0].content
    mapping = updates["_pii_pseudonym_map"]
    assert mapping["<<pii:email:1>>"] == "bob@work.com"

    # 2. Test ToolMessage (New Refactored Logic: Mask instead of Decode)
    tool_content = "The logs for 10.0.0.5 show errors"
    state = {
        "messages": [ToolMessage(content=tool_content, tool_call_id="call_1")],
        "_pii_pseudonym_map": mapping
    }
    updates = mw.before_model(state, None)
    assert updates is not None
    assert "10.0.0.5" not in updates["messages"][0].content
    assert "<<pii:ip:1>>" in updates["messages"][0].content
    assert updates["_pii_pseudonym_map"]["<<pii:ip:1>>"] == "10.0.0.5"

def test_middleware_pii_decoding_after_model():
    mw = PIIPseudonymizationMiddleware(apply_to_output=True, decode_tool_calls=True)
    mapping = {"<<pii:email:1>>": "secret@agent.com"}
    
    # AI wants to call a tool with the placeholder
    ai_msg = AIMessage(
        content="Sending email to <<pii:email:1>>",
        tool_calls=[{"name": "send_email", "args": {"to": "<<pii:email:1>>"}, "id": "call_1"}]
    )
    state = {"messages": [ai_msg], "_pii_pseudonym_map": mapping}
    
    updates = mw.after_model(state, None)
    assert updates is not None
    
    # 1. Content should be decoded (if apply_to_output is True)
    assert "secret@agent.com" in updates["messages"][0].content
    
    # 2. Tool calls MUST be decoded so the actual tool gets the real email
    assert updates["messages"][0].tool_calls[0]["args"]["to"] == "secret@agent.com"

def test_middleware_toggles():
    # Test that disabling input masking works
    mw = PIIPseudonymizationMiddleware(apply_to_input=False)
    state = {"messages": [HumanMessage(content="Keep my email bob@me.com")]}
    updates = mw.before_model(state, None)
    assert updates is None
