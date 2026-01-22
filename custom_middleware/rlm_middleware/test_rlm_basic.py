"""
Simple test script for RLM middleware.
Tests the middleware structure, tools, and REPL environment.
"""

import sys
import json
from io import StringIO
from rlm_middleware import REPLEnvironment, RLMConfig, RLMMiddleware

def test_repl_environment():
    """Test the REPL environment execution."""
    print("Testing REPL Environment...")
    
    # Test 1: Basic code execution
    context = "This is a test context with 100 devices"
    env = REPLEnvironment(context)
    
    code = """
# Test basic execution
result = len(context)
print(f"Context length: {result}")
"""
    
    result = env.execute(code)
    assert result['success'], "Code execution failed"
    # Note: Output keys might verify logic, but here we just check presence
    # Implementation details of extract logic are not tested here if not present in class
    assert 'Context length:' in result['output'], "Output not captured"
    print("✓ Basic execution works")
    
    # Test 2: Variable persistence
    code1 = "counter = 5"
    result1 = env.execute(code1)
    
    code2 = "counter += 3; print(counter)"
    result2 = env.execute(code2)
    
    assert result2['success'], "Variable persistence failed"
    assert '8' in result2['output'], "Variables not persisting"
    print("✓ Variable persistence works")
    
    # Test 3: Error handling
    code_error = "undefined_variable + 1"
    result_error = env.execute(code_error)
    
    assert not result_error['success'], "Error not caught"
    assert result_error['error'] is not None, "Error not reported"
    print("✓ Error handling works")
    
    print("\n✅ All REPL tests passed!\n")


def test_context_info():
    """Test context information extraction."""
    print("Testing Context Info...")
    
    # String context
    str_context = "A" * 1000
    env1 = REPLEnvironment(str_context)
    info1 = env1.get_context_info()
    
    assert info1['type'] == 'str', "Type detection failed"
    assert info1['total_chars'] == 1000, "Character count failed"
    print(f"✓ String context: {info1}")
    
    # Dict context
    dict_context = {'device1': 'data1', 'device2': 'data2'}
    env2 = REPLEnvironment(dict_context)
    info2 = env2.get_context_info()
    
    assert info2['type'] == 'dict', "Dict type detection failed"
    assert info2['length'] == 2, "Dict length failed"
    print(f"✓ Dict context: {info2}")
    
    print("\n✅ All context info tests passed!\n")


def test_config():
    """Test RLM configuration."""
    print("Testing Configuration...")
    
    # Default config
    config1 = RLMConfig()
    assert config1.max_iterations == 20, "Default iterations wrong"
    assert config1.enable_sub_calls == True, "Default sub_calls wrong"
    print(f"✓ Default config: {config1}")
    
    # Custom config
    config2 = RLMConfig(
        max_iterations=10,
        enable_sub_calls=False,
        max_recursion_depth=2
    )
    assert config2.max_iterations == 10, "Custom iterations wrong"
    assert config2.enable_sub_calls == False, "Custom sub_calls wrong"
    assert config2.max_recursion_depth == 2, "Custom depth wrong"
    print(f"✓ Custom config: iterations={config2.max_iterations}, depth={config2.max_recursion_depth}")
    
    print("\n✅ All config tests passed!\n")


def test_middleware():
    """Test RLMMiddleware structure and tools."""
    print("Testing RLMMiddleware...")
    
    # Mock LLM
    class MockLLM:
        def invoke(self, messages):
            # Simple mock response
            class Response:
                content = "mock content"
            return Response()
    
    # Instantiate middleware
    middleware = RLMMiddleware(model=MockLLM())
    
    # 1. Check tools
    tools = middleware.tools
    tool_names = [t.name for t in tools]
    print(f"Tools found: {tool_names}")
    
    expected_tools = ['rlm_load_context', 'rlm_execute_code', 'rlm_context_info']
    for tool_name in expected_tools:
        assert tool_name in tool_names, f"Missing tool: {tool_name}"
    
    # 2. Check System Prompt
    prompt = middleware.system_prompt
    assert "RLM (Recursive Language Model) Capabilities" in prompt
    assert "'context'" in prompt
    print("✓ System prompt generated successfully")
    
    # 3. Test Tool Execution: load_context
    load_tool = next(t for t in tools if t.name == 'rlm_load_context')
    
    # Load JSON data
    data = json.dumps({"foo": "bar", "num": 123})
    result = load_tool.invoke({"data": data})
    assert "Context loaded as JSON/Dict" in result
    
    # Verify via REPL
    execute_tool = next(t for t in tools if t.name == 'rlm_execute_code')
    check_code = "print(context['foo'])"
    exec_result = execute_tool.invoke({"code": check_code})
    assert "bar" in exec_result
    print("✓ rlm_load_context and rlm_execute_code working together")
    
    print("\n✅ All middleware tests passed!\n")


def run_all_tests():
    """Run all tests."""
    print("=" * 80)
    print("RLM MIDDLEWARE TEST SUITE")
    print("=" * 80)
    print()
    
    try:
        test_repl_environment()
        test_context_info()
        test_config()
        test_middleware()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
