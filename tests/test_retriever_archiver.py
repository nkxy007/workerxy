import os
import sys
import unittest
from pathlib import Path
import shutil

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Load credentials
try:
    import creds
    os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
except ImportError:
    pass

from tools_helpers.retriever_archiver import ArchiverRetriever, DocumentType

class TestRetrieverArchiver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a temporary directory for the vector store
        cls.test_storage_path = str(Path("/tmp/retriever_archiver_test"))
        if os.path.exists(cls.test_storage_path):
            shutil.rmtree(cls.test_storage_path)
        
        # Initialize the module
        cls.ra = ArchiverRetriever(storage_path=cls.test_storage_path)

    def test_01_conversation_archiving(self):
        print("\n--- Testing Conversation Archiving ---")
        messages = [
            {"role": "user", "content": "Hello! I am planning to build a new network for my home office."},
            {"role": "assistant", "content": "That sounds like a great project. What kind of equipment are you considering?"},
            {"role": "user", "content": "I'm thinking of using a Ubiquiti Dream Machine and some Pro access points."},
            {"role": "assistant", "content": "Ubiquiti is a solid choice. You'll want to ensure you have enough PoE capacity for those APs."}
        ]
        
        doc_id = self.ra.archive_conversation(messages, metadata={"project": "home_network"})
        print(f"Archived conversation with ID: {doc_id}")
        self.assertTrue(doc_id.startswith("conv_"))
        
        # Test retrieval
        results = self.ra.retrieve("Ubiquiti equipment", top_k=3)
        self.assertTrue(len(results) > 0)
        
        # Check if any of the retrieved chunks contain the key info
        found = any("Ubiquiti" in c.content for c in results)
        self.assertTrue(found, "Info about Ubiquiti should be in one of the retrieved chunks")
        self.assertEqual(results[0].metadata['project'], "home_network")
        print(f"Retrieved {len(results)} chunks, found info.")

    def test_02_documentation_archiving(self):
        print("\n--- Testing Documentation Archiving ---")
        # Create a mock markdown file with commands
        mock_file = "/tmp/test_commands.md"
        content = """# Network Setup Guide
        
This guide explains how to configure a Cisco router.

## Basic Configuration
To enter configuration mode, use:
```bash
configure terminal
```

Then set the hostname:
```bash
hostname Router1
```

## Verification
Use this command to see the interfaces:
```bash
show ip interface brief
```
"""
        with open(mock_file, 'w') as f:
            f.write(content)
            
        doc_id = self.ra.archive_documentation(mock_file)
        print(f"Archived documentation with ID: {doc_id}")
        self.assertEqual(doc_id, "test_commands")
        
        # Test command retrieval
        results = self.ra.retrieve("how to set hostname", top_k=3)
        self.assertTrue(len(results) > 0)
        
        # Check if any of the retrieved chunks contain the command
        found = any("hostname Router1" in c.content for c in results)
        self.assertTrue(found, "Command 'hostname Router1' should be in one of the retrieved chunks")
        
        # Verify that at least one chunk is correctly flagged as containing commands
        has_cmd_flag = any(c.metadata.get('contains_commands') for c in results)
        self.assertTrue(has_cmd_flag, "At least one retrieved chunk should be flagged as containing commands")
        print(f"Retrieved {len(results)} chunks, found command and flags.")

    def test_03_context_expansion(self):
        print("\n--- Testing Context Expansion ---")
        # Query for "interface brief" which should be in the last section
        results = self.ra.retrieve("interface brief", top_k=1, expand_window=1)
        
        # Since expand_window=1, it should retrieve the match + 1 chunk before/after
        # For this small doc, it might retrieve almost everything
        print(f"Found {len(results)} chunks in context")
        self.assertTrue(len(results) >= 1)
        
        # Verify content flow
        contents = [c.content for c in results]
        all_text = "\n".join(contents)
        self.assertIn("show ip interface brief", all_text)

    def test_04_rag_query(self):
        print("\n--- Testing RAG Query ---")
        query = "What command is used to set the hostname in the guide?"
        result = self.ra.rag_query(query)
        print(f"RAG Answer: {result['answer']}")
        self.assertIn("hostname Router1", result['answer'])
        self.assertIn("test_commands", result['sources'])

    def test_05_time_awareness(self):
        print("\n--- Testing Time-Aware Retrieval ---")
        # Archive two versions of the same info with different timestamps (simulated by sequence)
        conv_old = [
            {"role": "user", "content": "What is the recommended router for the core?"},
            {"role": "assistant", "content": "I recommend the Cisco ISR 4451."}
        ]
        self.ra.archive_conversation(conv_old, doc_id="old_config")
        
        conv_new = [
            {"role": "user", "content": "Wait, we changed the core router plan."},
            {"role": "assistant", "content": "Okay, the new recommendation is the Cisco Catalyst 8300."}
        ]
        import time
        time.sleep(1.1) # Ensure different timestamp
        self.ra.archive_conversation(conv_new, doc_id="new_config")
        
        query = "What is the current recommended core router?"
        result = self.ra.rag_query(query)
        print(f"Time-Aware RAG Answer: {result['answer']}")
        
        # LLM should prioritize the Catalyst 8300 based on the instruction to favor newer info
        self.assertIn("Catalyst 8300", result['answer'])
        self.assertIn("8300", result['answer'])
        print("Successfully prioritized newer information.")

    def test_06_robust_command_detection(self):
        print("\n--- Testing Robust Command Detection ---")
        content = """# System Admin Guide

## Bash script
Look at this shebang:
#!/bin/bash
echo "Hello"

## Shell prompts
Here is a normal prompt:
user@host:~$ ls -la

And a root prompt:
root@server:/# apt-get update

## Cisco prompts
Switch(config)# interface Gi0/1
Switch(config-if)# no shutdown

## Generic binary / manual commands
/usr/bin/python3 -m venv venv
ping 8.8.8.8 -c 4
"""
        mock_file = "/tmp/robust_commands.md"
        with open(mock_file, 'w') as f:
            f.write(content)
            
        doc_id = self.ra.archive_documentation(mock_file)
        
        # We retrieve chunks and check metadata
        # Given the markdown chunker, it might split by headers
        # Let's check chunks containing the keywords
        results = self.ra.retrieve("apt-get update", top_k=5)
        for chunk in results:
            if "apt-get update" in chunk.content or "Switch(config)#" in chunk.content or "#!/bin/bash" in chunk.content:
                self.assertTrue(chunk.metadata.get('contains_commands'), f"Chunk containing commands should be flagged. Content: {chunk.content[:30]}...")
        
        print("Successfully verified robust command detection flagging.")

    @classmethod
    def tearDownClass(cls):

        # Clean up
        if os.path.exists(cls.test_storage_path):
            shutil.rmtree(cls.test_storage_path)

if __name__ == "__main__":
    unittest.main()
