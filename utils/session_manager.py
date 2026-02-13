"""
Session manager utility for handling user sessions.
Manages session state, message history, and clarification queues.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
import threading
from .session_persistence import SessionPersistence


class SessionManager:
    """Manages user sessions for the agent system."""

    def __init__(self, persistence_handler: Optional[SessionPersistence] = None, auto_save: bool = False):
        """
        Initialize SessionManager.
        
        Args:
            persistence_handler: Optional persistence handler for disk operations
            auto_save: Whether to automatically save to disk on changes
        """
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.persistence_handler = persistence_handler
        self.auto_save = auto_save

    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new session.

        Args:
            session_id: Optional session ID. If not provided, generates UUID.

        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    'created_at': datetime.now().isoformat(),
                    'last_activity': datetime.now().isoformat(),
                    'messages': [],
                    'clarification_queue': [],
                    'clarification_responses': [],
                    'artifacts': [],
                    'stream_logs': [],
                    'errors': [],
                    'uploaded_files': {
                        'documents': [],
                        'diagrams': []
                    },
                    'metadata': {}
                }

        if self.auto_save:
            self.save_to_disk(session_id)

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        with self.lock:
            return self.sessions.get(session_id)

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        return session_id in self.sessions

    def update_activity(self, session_id: str):
        """
        Update last activity timestamp for session.

        Args:
            session_id: Session identifier
        """
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['last_activity'] = datetime.now().isoformat()

    # Message management

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add message to session history.

        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata dict
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }

        with self.lock:
            self.sessions[session_id]['messages'].append(message)
            # Update activity directly (don't call update_activity which would deadlock)
            if session_id in self.sessions:
                self.sessions[session_id]['last_activity'] = datetime.now().isoformat()

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get message history for session.

        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages to return

        Returns:
            List of messages
        """
        session = self.get_session(session_id)
        if not session:
            return []

        messages = session['messages']
        if limit:
            return messages[-limit:]
        return messages

    def get_messages_for_agent(self, session_id: str) -> List[Dict]:
        """
        Get messages formatted for agent consumption.

        Args:
            session_id: Session identifier

        Returns:
            List of message dicts with role and content
        """
        messages = self.get_messages(session_id)
        return [{'role': msg['role'], 'content': msg['content']} for msg in messages]

    # Clarification management

    def add_clarification_request(self, session_id: str, question: str, intention: str = ""):
        """
        Add clarification request to queue.

        Args:
            session_id: Session identifier
            question: Clarification question
            intention: Optional intention behind the question
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        clarification = {
            'question': question,
            'intention': intention,
            'timestamp': datetime.now().isoformat(),
            'answered': False
        }

        with self.lock:
            self.sessions[session_id]['clarification_queue'].append(clarification)

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_pending_clarifications(self, session_id: str) -> List[Dict]:
        """
        Get pending clarification requests.

        Args:
            session_id: Session identifier

        Returns:
            List of pending clarification requests
        """
        session = self.get_session(session_id)
        if not session:
            return []

        return [c for c in session['clarification_queue'] if not c['answered']]

    def add_clarification_response(self, session_id: str, response: str):
        """
        Add response to clarification question.

        Args:
            session_id: Session identifier
            response: User's response
        """
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['clarification_responses'].append(response)

                # Mark first unanswered clarification as answered
                for clarification in self.sessions[session_id]['clarification_queue']:
                    if not clarification['answered']:
                        clarification['answered'] = True
                        clarification['response'] = response
                        clarification['answered_at'] = datetime.now().isoformat()
                        break

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_clarification_response(self, session_id: str) -> Optional[str]:
        """
        Get next clarification response from queue.

        Args:
            session_id: Session identifier

        Returns:
            Response string or None if queue is empty
        """
        with self.lock:
            session = self.get_session(session_id)
            if session and session['clarification_responses']:
                return session['clarification_responses'].pop(0)
        return None

    # Artifact management

    def add_artifact(self, session_id: str, artifact: Dict[str, Any]):
        """
        Add artifact to session.

        Args:
            session_id: Session identifier
            artifact: Artifact dictionary with name, type, content, etc.
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        artifact['timestamp'] = datetime.now().isoformat()

        with self.lock:
            self.sessions[session_id]['artifacts'].append(artifact)

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_artifacts(self, session_id: str) -> List[Dict]:
        """
        Get artifacts for session.

        Args:
            session_id: Session identifier

        Returns:
            List of artifacts
        """
        session = self.get_session(session_id)
        if not session:
            return []
        return session['artifacts']

    # Stream logs management

    def add_stream_log(self, session_id: str, event: str, details: str, metadata: Optional[Dict] = None):
        """
        Add stream log entry.

        Args:
            session_id: Session identifier
            event: Event name
            details: Event details
            metadata: Optional metadata
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        log_entry = {
            'event': event,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }

        with self.lock:
            self.sessions[session_id]['stream_logs'].append(log_entry)

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_stream_logs(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get stream logs for session.

        Args:
            session_id: Session identifier
            limit: Optional limit on number of logs

        Returns:
            List of log entries
        """
        session = self.get_session(session_id)
        if not session:
            return []

        logs = session['stream_logs']
        if limit:
            return logs[-limit:]
        return logs

    # Error management

    def add_error(self, session_id: str, error_message: str, traceback_str: Optional[str] = None):
        """
        Add error to session.

        Args:
            session_id: Session identifier
            error_message: Error message
            traceback_str: Optional traceback string
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        error = {
            'message': error_message,
            'traceback': traceback_str,
            'timestamp': datetime.now().isoformat()
        }

        with self.lock:
            self.sessions[session_id]['errors'].append(error)

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_errors(self, session_id: str) -> List[Dict]:
        """
        Get errors for session.

        Args:
            session_id: Session identifier

        Returns:
            List of errors
        """
        session = self.get_session(session_id)
        if not session:
            return []
        return session['errors']

    # File management

    def add_uploaded_file(self, session_id: str, file_type: str, file_info: Dict):
        """
        Record uploaded file.

        Args:
            session_id: Session identifier
            file_type: 'document' or 'diagram'
            file_info: File information dict
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        with self.lock:
            if file_type in ['document', 'diagram']:
                self.sessions[session_id]['uploaded_files'][f'{file_type}s'].append(file_info)

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_uploaded_files(self, session_id: str) -> Dict[str, List]:
        """
        Get uploaded files for session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with 'documents' and 'diagrams' lists
        """
        session = self.get_session(session_id)
        if not session:
            return {'documents': [], 'diagrams': []}
        return session['uploaded_files']

    # Metadata management

    def set_metadata(self, session_id: str, key: str, value: Any):
        """
        Set metadata for session.

        Args:
            session_id: Session identifier
            key: Metadata key
            value: Metadata value
        """
        if not self.session_exists(session_id):
            self.create_session(session_id)

        with self.lock:
            self.sessions[session_id]['metadata'][key] = value

        if self.auto_save:
            self.save_to_disk(session_id)

    def get_metadata(self, session_id: str, key: str) -> Optional[Any]:
        """
        Get metadata value.

        Args:
            session_id: Session identifier
            key: Metadata key

        Returns:
            Metadata value or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        return session['metadata'].get(key)

    # Session cleanup

    def clear_session(self, session_id: str):
        """
        Clear session data.

        Args:
            session_id: Session identifier
        """
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

    def get_all_sessions(self) -> List[str]:
        """
        Get all session IDs.

        Returns:
            List of session IDs
        """
        return list(self.sessions.keys())

    def get_session_count(self) -> int:
        """
        Get number of active sessions.

        Returns:
            Number of sessions
        """
        return len(self.sessions)
    # Persistence Operations

    def enable_persistence(self, persistence_handler: SessionPersistence, auto_save: bool = True):
        """
        Enable session persistence.

        Args:
            persistence_handler: SessionPersistence instance
            auto_save: Whether to enable auto-save
        """
        self.persistence_handler = persistence_handler
        self.auto_save = auto_save

    def save_to_disk(self, session_id: str, metadata: Optional[Dict] = None) -> bool:
        """
        Save session to disk.

        Args:
            session_id: Session identifier
            metadata: Optional metadata updates

        Returns:
            True if successful
        """
        if not self.persistence_handler:
            return False

        session_data = self.get_session(session_id)
        if not session_data:
            return False

        success, error = self.persistence_handler.save_session(
            session_id, session_data, metadata
        )
        return success

    def load_from_disk(self, session_id: str) -> bool:
        """
        Load session from disk into memory.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        if not self.persistence_handler:
            return False

        success, session_data, error = self.persistence_handler.load_session(session_id)
        if success and session_data:
            with self.lock:
                self.sessions[session_id] = session_data
            return True
        return False

    def delete_from_disk(self, session_id: str) -> bool:
        """
        Delete session from disk and memory.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        # Delete from disk first
        disk_success = True
        if self.persistence_handler:
            disk_success, error = self.persistence_handler.delete_session(session_id)

        # Delete from memory
        self.clear_session(session_id)
        
        return disk_success

    def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata on disk.

        Args:
            session_id: Session identifier
            metadata_updates: Fields to update

        Returns:
            True if successful
        """
        if not self.persistence_handler:
            return False
            
        success, error = self.persistence_handler.update_metadata(session_id, metadata_updates)
        return success
