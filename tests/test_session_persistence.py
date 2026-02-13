"""
Unit tests for SessionPersistence utility.
"""

import unittest
import shutil
import json
import os
from pathlib import Path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from utils.session_persistence import SessionPersistence

class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_sessions")
        self.persistence = SessionPersistence(base_dir=str(self.test_dir))
        self.session_id = "test-session-123"
        self.session_data = {
            "session_id": self.session_id,
            "created_at": "2026-02-12T10:00:00",
            "messages": [{"role": "user", "content": "Hello agent"}],
            "artifacts": []
        }

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_save_and_load_session(self):
        # Save
        success, error = self.persistence.save_session(self.session_id, self.session_data)
        self.assertTrue(success)
        self.assertIsNone(error)

        # Load
        success, loaded_data, error = self.persistence.load_session(self.session_id)
        self.assertTrue(success)
        self.assertEqual(loaded_data["session_id"], self.session_id)
        self.assertEqual(len(loaded_data["messages"]), 1)

    def test_list_sessions(self):
        self.persistence.save_session("session-1", self.session_data)
        self.persistence.save_session("session-2", self.session_data)
        
        sessions = self.persistence.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_delete_session(self):
        self.persistence.save_session(self.session_id, self.session_data)
        self.assertTrue(self.persistence.session_exists(self.session_id))
        
        success, error = self.persistence.delete_session(self.session_id)
        self.assertTrue(success)
        self.assertFalse(self.persistence.session_exists(self.session_id))

    def test_metadata_generation(self):
        self.persistence.save_session(self.session_id, self.session_data)
        metadata = self.persistence.get_metadata(self.session_id)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["title"], "Hello agent")
        self.assertEqual(metadata["message_count"], 1)

    def test_invalid_session_id(self):
        success, error = self.persistence.save_session("../invalid", self.session_data)
        self.assertFalse(success)
        self.assertIn("Invalid session ID", error)

if __name__ == '__main__':
    unittest.main()
