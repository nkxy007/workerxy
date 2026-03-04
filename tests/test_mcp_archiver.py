import os
import sys
import asyncio
import unittest
from pathlib import Path
import shutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Load credentials
from utils.credentials_helper import get_helper
get_helper()

# Import the mcp server functions
# We import from mcp_servers to test the tools as they are registered
from mcp_servers import archive_current_conversation, archive_local_document, query_agent_archives

class TestMCPArchiverTools(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # The ArchiverRetriever in mcp_servers.py will use the default path: ~/.net-deepagent/archives
        # For testing, we might want to isolate it, but mcp_servers.py initializes it at module level.
        # So we just test if the tools respond correctly.
        pass

    async def test_01_mcp_archive_conversation(self):
        print("\n--- Testing MCP archive_current_conversation ---")
        messages = [
            {"role": "user", "content": "Our secret project code name is 'Stellar'."},
            {"role": "assistant", "content": "Acknowledged. I will remember that our project code name is 'Stellar'."}
        ]
        
        result = await archive_current_conversation(
            messages=messages, 
            intention="testing mcp tool", 
            metadata={"test": "mcp"}
        )
        print(f"Result: {result}")
        self.assertIn("successfully", result)

    async def test_02_mcp_archive_document(self):
        print("\n--- Testing MCP archive_local_document ---")
        mock_file = "/tmp/mcp_test_doc.md"
        with open(mock_file, "w") as f:
            f.write("# Protocol 9\n\nProtocol 9 requires all nodes to reboot at midnight.")
            
        result = await archive_local_document(
            file_path=mock_file, 
            intention="testing mcp tool"
        )
        print(f"Result: {result}")
        self.assertIn("successfully", result)

    async def test_03_mcp_query_archives(self):
        print("\n--- Testing MCP query_agent_archives ---")
        # Test recalling conversation
        result = await query_agent_archives(
            query="What is our project code name?", 
            intention="testing mcp tool"
        )
        print(f"Conversation recall result:\n{result}")
        self.assertIn("Stellar", result)
        
        # Test recalling document
        result = await query_agent_archives(
            query="What does Protocol 9 require?", 
            intention="testing mcp tool"
        )
        print(f"Document recall result:\n{result}")
        self.assertIn("reboot", result)
        self.assertIn("midnight", result)

if __name__ == "__main__":
    unittest.main()
