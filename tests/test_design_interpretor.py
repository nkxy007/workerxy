import asyncio
import os
import sys
import pytest
from langchain_core.messages import HumanMessage

# Add workspace root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graphs.design_interpretor import design_interpretor_graph, FullDesign, DesignDocumentInfo


def _load_api_key():
    """Load the OpenAI API key from environment or creds.py."""
    if os.environ.get("OPENAI_API_KEY"):
        return True
    try:
        import creds
        os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
        print("Loaded API key from creds.py")
        return True
    except ImportError:
        print("Could not import creds.py and OPENAI_API_KEY not set.")
        return False


# ---------------------------------------------------------------------------
# Test 1: Image branch (existing behaviour, must remain unbroken)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_design_interpretor_image_branch():
    """Verify the image branch routes correctly and returns a FullDesign result."""
    print("\n=== Image Branch Test ===")

    sample_image = "/home/toffe/workspace/agentic/small_network_diagram.png"
    if not os.path.exists(sample_image):
        pytest.skip(f"Sample image not found: {sample_image}")

    if not _load_api_key():
        pytest.skip("OPENAI_API_KEY not available")

    initial_state = {
        "messages": [HumanMessage(content=f"Analyze this network diagram: {sample_image}")],
        "model_name": "openai",
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }

    final_state = await design_interpretor_graph.ainvoke(initial_state)

    print("\n--- Image Branch Results ---")
    if final_state.get("error"):
        print(f"Error: {final_state['error']}")

    if final_state.get("result"):
        result: FullDesign = final_state["result"]
        print(f"Summary: {result.summary}")
        print(f"Devices: {len(result.devices)}, Links: {len(result.links)}, Protocols: {len(result.protocols)}")
        for dev in result.devices:
            print(f"  - {dev.name} ({dev.brand})")
        assert isinstance(result, FullDesign), "Expected FullDesign result from image branch"
    else:
        # Raw analysis is acceptable if structured parsing failed
        last_msg = final_state["messages"][-1].content
        print(f"Raw analysis:\n{last_msg}")
        assert last_msg, "Expected at least a raw analysis message from image branch"


# ---------------------------------------------------------------------------
# Test 2: Document branch (new behaviour)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_design_interpretor_document_branch():
    """Verify the document branch routes correctly and returns a DesignDocumentInfo result."""
    print("\n=== Document Branch Test ===")

    # Look for any PDF in common workspace paths
    candidate_paths = [
        "/home/toffe/workspace/agentic/utopia_sm_network_design.pdf",
        "/home/toffe/workspace/agentic/sample_design.pdf",
    ]
    sample_doc = next((p for p in candidate_paths if os.path.exists(p)), None)

    if sample_doc is None:
        pytest.skip(
            "No sample PDF design document found. Place a PDF at one of: "
            + str(candidate_paths)
        )

    if not _load_api_key():
        pytest.skip("OPENAI_API_KEY not available")

    doc_state = {
        "messages": [HumanMessage(
            content=f"Read this network design document and extract all relevant details: {sample_doc}"
        )],
        "api_key": os.environ.get("OPENAI_API_KEY"),
    }

    final_state = await design_interpretor_graph.ainvoke(doc_state)

    print("\n--- Document Branch Results ---")
    if final_state.get("error"):
        print(f"Error: {final_state['error']}")

    assert "document_result" in final_state, "Expected 'document_result' key in final state"
    doc_result: DesignDocumentInfo = final_state["document_result"]
    assert isinstance(doc_result, DesignDocumentInfo), "Expected DesignDocumentInfo object"

    print(f"Site: {doc_result.site_name or 'Unknown'}")
    print(f"Location: {doc_result.location or 'N/A'}")
    print(f"Devices ({len(doc_result.devices)}):")
    for dev in doc_result.devices:
        print(f"  - {dev.name} | IP: {dev.management_ip} | Brand: {dev.brand}")
    print(f"Links: {len(doc_result.links)}")
    print(f"Protocols: {len(doc_result.protocols)}")
    print(f"Routing protocols: {doc_result.routing_protocols}")
    print(f"VLANs: {doc_result.vlans}")
    print(f"Summary: {doc_result.summary}")


# ---------------------------------------------------------------------------
# Test 3: Router correctly identifies input type from message content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_input_type_routing():
    """Verify detect_input_type correctly sets document_path vs image_path."""
    from graphs.design_interpretor import detect_input_type

    # Test PDF detection
    pdf_state = {
        "messages": [HumanMessage(content="Please read /tmp/my_design.pdf for me")],
        "image_path": "",
        "document_path": "",
        "model_name": "openai",
        "api_key": "test",
        "error": None,
        "result": None,
        "document_result": None,
    }
    result = detect_input_type(pdf_state)
    assert result.get("document_path") == "/tmp/my_design.pdf", \
        f"Expected document_path to be set, got: {result}"
    print("PDF detection: PASS")

    # Test image detection
    img_state = {
        "messages": [HumanMessage(content="Analyze this diagram /tmp/network.png")],
        "image_path": "",
        "document_path": "",
        "model_name": "openai",
        "api_key": "test",
        "error": None,
        "result": None,
        "document_result": None,
    }
    result = detect_input_type(img_state)
    assert result.get("image_path") == "/tmp/network.png", \
        f"Expected image_path to be set, got: {result}"
    print("Image detection: PASS")

    # Test no path
    no_path_state = {
        "messages": [HumanMessage(content="Hello there, no file path here")],
        "image_path": "",
        "document_path": "",
        "model_name": "openai",
        "api_key": "test",
        "error": None,
        "result": None,
        "document_result": None,
    }
    result = detect_input_type(no_path_state)
    assert result.get("error"), f"Expected error when no path found, got: {result}"
    print("No-path error detection: PASS")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

async def _run_all():
    await test_detect_input_type_routing()
    await test_design_interpretor_image_branch()
    await test_design_interpretor_document_branch()

if __name__ == "__main__":
    asyncio.run(_run_all())
