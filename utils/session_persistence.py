"""
Session persistence utility for saving and loading sessions to/from disk.
Handles session serialization, storage, and retrieval.
"""

import json
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import threading
import os

logger = logging.getLogger(__name__)


class SessionPersistence:
    """Manages session persistence to disk."""

    def __init__(self, base_dir: str = "~/.net_deepagent/sessions"):
        """
        Initialize SessionPersistence.

        Args:
            base_dir: Base directory for session storage
        """
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        logger.info(f"SessionPersistence initialized with base_dir: {self.base_dir}")

    def _get_session_dir(self, session_id: str) -> Path:
        """
        Get directory path for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to session directory
        """
        return self.base_dir / session_id

    def _validate_session_id(self, session_id: str) -> bool:
        """
        Validate session ID format.

        Args:
            session_id: Session identifier to validate

        Returns:
            True if valid
        """
        # Basic validation - should be a valid UUID or safe string
        if not session_id or len(session_id) > 100:
            return False
        # Check for path traversal attempts
        if ".." in session_id or "/" in session_id or "\\" in session_id:
            return False
        return True

    def save_session(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Save session to disk.

        Args:
            session_id: Session identifier
            session_data: Complete session data dictionary
            metadata: Optional metadata (title, preview, tags, etc.)

        Returns:
            Tuple of (success, error_message)
        """
        if not self._validate_session_id(session_id):
            return False, "Invalid session ID"

        try:
            with self.lock:
                session_dir = self._get_session_dir(session_id)
                session_dir.mkdir(parents=True, exist_ok=True)

                # Save session data
                session_file = session_dir / "session.json"
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2, ensure_ascii=False)

                # Generate or update metadata
                if metadata is None:
                    metadata = self._generate_metadata(session_id, session_data)
                else:
                    # Ensure required fields are present
                    metadata.setdefault('session_id', session_id)
                    metadata.setdefault('last_activity', datetime.now().isoformat())
                    metadata.setdefault('version', '1.0')

                # Save metadata
                metadata_file = session_dir / "metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                logger.info(f"Session {session_id} saved successfully")
                return True, None

        except Exception as e:
            error_msg = f"Error saving session {session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def load_session(self, session_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Load session from disk.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (success, session_data, error_message)
        """
        if not self._validate_session_id(session_id):
            return False, None, "Invalid session ID"

        try:
            session_dir = self._get_session_dir(session_id)
            session_file = session_dir / "session.json"

            if not session_file.exists():
                return False, None, f"Session {session_id} not found"

            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            logger.info(f"Session {session_id} loaded successfully")
            return True, session_data, None

        except json.JSONDecodeError as e:
            error_msg = f"Corrupted session file for {session_id}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Error loading session {session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    def list_sessions(
        self,
        sort_by: str = 'last_activity',
        reverse: bool = True,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List all saved sessions with metadata.

        Args:
            sort_by: Field to sort by ('last_activity', 'created_at', 'title')
            reverse: Sort in reverse order (newest first)
            limit: Optional limit on number of sessions to return

        Returns:
            List of session metadata dictionaries
        """
        sessions = []

        try:
            for session_dir in self.base_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                metadata_file = session_dir / "metadata.json"
                if not metadata_file.exists():
                    # Try to generate metadata from session file
                    session_file = session_dir / "session.json"
                    if session_file.exists():
                        try:
                            with open(session_file, 'r', encoding='utf-8') as f:
                                session_data = json.load(f)
                            metadata = self._generate_metadata(session_dir.name, session_data)
                            # Save generated metadata
                            with open(metadata_file, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            logger.warning(f"Could not generate metadata for {session_dir.name}: {e}")
                            continue
                    else:
                        continue

                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    sessions.append(metadata)
                except Exception as e:
                    logger.warning(f"Could not load metadata for {session_dir.name}: {e}")
                    continue

            # Sort sessions
            if sort_by in ['last_activity', 'created_at']:
                sessions.sort(
                    key=lambda x: x.get(sort_by, ''),
                    reverse=reverse
                )
            elif sort_by == 'title':
                sessions.sort(
                    key=lambda x: x.get('title', '').lower(),
                    reverse=reverse
                )

            # Apply limit
            if limit:
                sessions = sessions[:limit]

            return sessions

        except Exception as e:
            logger.error(f"Error listing sessions: {e}", exc_info=True)
            return []

    def delete_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a saved session.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (success, error_message)
        """
        if not self._validate_session_id(session_id):
            return False, "Invalid session ID"

        try:
            with self.lock:
                session_dir = self._get_session_dir(session_id)

                if not session_dir.exists():
                    return False, f"Session {session_id} not found"

                shutil.rmtree(session_dir)
                logger.info(f"Session {session_id} deleted successfully")
                return True, None

        except Exception as e:
            error_msg = f"Error deleting session {session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists on disk.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        if not self._validate_session_id(session_id):
            return False

        session_dir = self._get_session_dir(session_id)
        session_file = session_dir / "session.json"
        return session_file.exists()

    def get_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a session.

        Args:
            session_id: Session identifier

        Returns:
            Metadata dictionary or None if not found
        """
        if not self._validate_session_id(session_id):
            return None

        try:
            session_dir = self._get_session_dir(session_id)
            metadata_file = session_dir / "metadata.json"

            if not metadata_file.exists():
                return None

            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error loading metadata for {session_id}: {e}")
            return None

    def update_metadata(
        self,
        session_id: str,
        metadata_updates: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Update session metadata.

        Args:
            session_id: Session identifier
            metadata_updates: Dictionary of metadata fields to update

        Returns:
            Tuple of (success, error_message)
        """
        if not self._validate_session_id(session_id):
            return False, "Invalid session ID"

        try:
            with self.lock:
                session_dir = self._get_session_dir(session_id)
                metadata_file = session_dir / "metadata.json"

                # Load existing metadata
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                else:
                    metadata = {'session_id': session_id, 'version': '1.0'}

                # Update fields
                metadata.update(metadata_updates)
                metadata['last_activity'] = datetime.now().isoformat()

                # Save updated metadata
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                logger.info(f"Metadata updated for session {session_id}")
                return True, None

        except Exception as e:
            error_msg = f"Error updating metadata for {session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def _generate_metadata(
        self,
        session_id: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate metadata from session data.

        Args:
            session_id: Session identifier
            session_data: Session data dictionary

        Returns:
            Metadata dictionary
        """
        messages = session_data.get('messages', [])
        artifacts = session_data.get('artifacts', [])
        uploaded_files = session_data.get('uploaded_files', {})

        # Generate title from first user message
        title = "Untitled Session"
        preview = ""
        if messages:
            first_user_msg = next(
                (msg for msg in messages if msg.get('role') == 'user'),
                None
            )
            if first_user_msg:
                content = first_user_msg.get('content', '')
                # Use first 50 chars as title
                title = content[:50].strip()
                if len(content) > 50:
                    title += "..."
                # Use first 150 chars as preview
                preview = content[:150].strip()
                if len(content) > 150:
                    preview += "..."

        # Count files
        file_count = (
            len(uploaded_files.get('documents', [])) +
            len(uploaded_files.get('diagrams', []))
        )

        return {
            'session_id': session_id,
            'title': title,
            'preview': preview,
            'created_at': session_data.get('created_at', datetime.now().isoformat()),
            'last_activity': session_data.get('last_activity', datetime.now().isoformat()),
            'message_count': len(messages),
            'artifact_count': len(artifacts),
            'file_count': file_count,
            'version': '1.0'
        }

    def export_session(
        self,
        session_id: str,
        output_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Export session as a compressed archive.

        Args:
            session_id: Session identifier
            output_path: Path for output archive (without extension)

        Returns:
            Tuple of (success, error_message)
        """
        if not self._validate_session_id(session_id):
            return False, "Invalid session ID"

        try:
            session_dir = self._get_session_dir(session_id)

            if not session_dir.exists():
                return False, f"Session {session_id} not found"

            # Create zip archive
            archive_path = shutil.make_archive(
                output_path,
                'zip',
                self.base_dir,
                session_id
            )

            logger.info(f"Session {session_id} exported to {archive_path}")
            return True, None

        except Exception as e:
            error_msg = f"Error exporting session {session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def import_session(
        self,
        archive_path: str,
        new_session_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Import session from a compressed archive.

        Args:
            archive_path: Path to archive file
            new_session_id: Optional new session ID (generates one if not provided)

        Returns:
            Tuple of (success, session_id, error_message)
        """
        try:
            import zipfile
            import uuid

            archive_path = Path(archive_path)
            if not archive_path.exists():
                return False, None, f"Archive not found: {archive_path}"

            # Extract to temporary directory
            temp_dir = self.base_dir / f"temp_import_{uuid.uuid4().hex[:8]}"
            temp_dir.mkdir(parents=True, exist_ok=True)

            try:
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Find the session directory (should be the only directory)
                session_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
                if not session_dirs:
                    return False, None, "No session directory found in archive"

                extracted_dir = session_dirs[0]

                # Validate session files
                session_file = extracted_dir / "session.json"
                if not session_file.exists():
                    return False, None, "Invalid session archive: missing session.json"

                # Generate new session ID if needed
                if new_session_id is None:
                    new_session_id = str(uuid.uuid4())

                if not self._validate_session_id(new_session_id):
                    return False, None, "Invalid session ID"

                # Check for conflicts
                target_dir = self._get_session_dir(new_session_id)
                if target_dir.exists():
                    return False, None, f"Session {new_session_id} already exists"

                # Move to final location
                shutil.move(str(extracted_dir), str(target_dir))

                # Update session ID in files
                with open(target_dir / "session.json", 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                # Update metadata if exists
                metadata_file = target_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    metadata['session_id'] = new_session_id
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                logger.info(f"Session imported as {new_session_id}")
                return True, new_session_id, None

            finally:
                # Clean up temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)

        except Exception as e:
            error_msg = f"Error importing session: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """
        Clean up sessions older than specified days.

        Args:
            days_old: Number of days to keep sessions

        Returns:
            Number of sessions cleaned up
        """
        count = 0
        current_time = datetime.now().timestamp()
        cutoff_time = current_time - (days_old * 24 * 60 * 60)

        try:
            for session_dir in self.base_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                # Check last activity from metadata
                metadata_file = session_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        last_activity = metadata.get('last_activity', '')
                        if last_activity:
                            last_time = datetime.fromisoformat(last_activity).timestamp()
                            if last_time < cutoff_time:
                                shutil.rmtree(session_dir)
                                count += 1
                                logger.info(f"Cleaned up old session: {session_dir.name}")
                    except Exception as e:
                        logger.warning(f"Error checking session {session_dir.name}: {e}")
                else:
                    # Fall back to directory modification time
                    mtime = session_dir.stat().st_mtime
                    if mtime < cutoff_time:
                        shutil.rmtree(session_dir)
                        count += 1
                        logger.info(f"Cleaned up old session: {session_dir.name}")

            logger.info(f"Cleanup complete: {count} sessions removed")
            return count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            return count
