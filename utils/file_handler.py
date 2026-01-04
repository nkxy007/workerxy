"""
File handler utility for managing file uploads and storage.
Handles document uploads (design docs, diagrams) for the agent system.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from datetime import datetime
import hashlib


class FileHandler:
    """Manages file uploads, storage, and cleanup for user sessions."""

    # Supported file types
    SUPPORTED_DOCUMENTS = {'.pdf', '.docx', '.doc', '.txt', '.md'}
    SUPPORTED_DIAGRAMS = {'.png', '.jpg', '.jpeg', '.svg', '.gif', '.bmp'}

    # File size limits (in bytes)
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_DIAGRAM_SIZE = 5 * 1024 * 1024    # 5 MB

    def __init__(self, base_upload_dir: str = "user_chat_files"):
        """
        Initialize FileHandler.

        Args:
            base_upload_dir: Base directory for all file uploads
        """
        self.base_upload_dir = Path(base_upload_dir)
        self.base_upload_dir.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session_id: str) -> Path:
        """
        Get or create directory for a specific session.

        Args:
            session_id: Unique session identifier

        Returns:
            Path to session directory
        """
        session_dir = self.base_upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def validate_file(
        self,
        filename: str,
        file_size: int,
        file_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file.

        Args:
            filename: Name of the file
            file_size: Size of file in bytes
            file_type: Type of file ('document' or 'diagram')

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get file extension
        file_ext = Path(filename).suffix.lower()

        # Check file type
        if file_type == 'document':
            if file_ext not in self.SUPPORTED_DOCUMENTS:
                return False, f"Unsupported document type: {file_ext}. Supported: {', '.join(self.SUPPORTED_DOCUMENTS)}"
            if file_size > self.MAX_DOCUMENT_SIZE:
                return False, f"Document too large: {file_size / 1024 / 1024:.2f} MB. Max: {self.MAX_DOCUMENT_SIZE / 1024 / 1024} MB"

        elif file_type == 'diagram':
            if file_ext not in self.SUPPORTED_DIAGRAMS:
                return False, f"Unsupported diagram type: {file_ext}. Supported: {', '.join(self.SUPPORTED_DIAGRAMS)}"
            if file_size > self.MAX_DIAGRAM_SIZE:
                return False, f"Diagram too large: {file_size / 1024 / 1024:.2f} MB. Max: {self.MAX_DIAGRAM_SIZE / 1024 / 1024} MB"

        else:
            return False, f"Unknown file type: {file_type}"

        return True, None

    def save_file(
        self,
        file_data: BinaryIO,
        filename: str,
        session_id: str,
        file_type: str
    ) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Save uploaded file to session directory.

        Args:
            file_data: Binary file data
            filename: Original filename
            session_id: Session identifier
            file_type: Type of file ('document' or 'diagram')

        Returns:
            Tuple of (success, error_message, file_path)
        """
        try:
            # Get session directory
            session_dir = self.get_session_dir(session_id)

            # Create subdirectory for file type
            type_dir = session_dir / file_type
            type_dir.mkdir(exist_ok=True)

            # Generate safe filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = self._sanitize_filename(filename)
            file_ext = Path(filename).suffix
            final_filename = f"{timestamp}_{safe_filename}"

            # Save file
            file_path = type_dir / final_filename

            # Read and validate file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset to beginning

            # Validate
            is_valid, error_msg = self.validate_file(filename, file_size, file_type)
            if not is_valid:
                return False, error_msg, None

            # Write file
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file_data, f)

            return True, None, file_path

        except Exception as e:
            return False, f"Error saving file: {str(e)}", None

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove potentially dangerous characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove extension for processing
        name = Path(filename).stem
        ext = Path(filename).suffix

        # Replace spaces and special chars
        safe_chars = []
        for char in name:
            if char.isalnum() or char in ('_', '-', '.'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')

        safe_name = ''.join(safe_chars)

        # Limit length
        if len(safe_name) > 50:
            safe_name = safe_name[:50]

        return safe_name + ext

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get information about a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file information
        """
        if not file_path.exists():
            return {}

        stat = file_path.stat()
        return {
            'filename': file_path.name,
            'size': stat.st_size,
            'size_mb': stat.st_size / 1024 / 1024,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'path': str(file_path),
            'extension': file_path.suffix
        }

    def list_session_files(self, session_id: str) -> dict:
        """
        List all files for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with 'documents' and 'diagrams' lists
        """
        session_dir = self.get_session_dir(session_id)

        result = {
            'documents': [],
            'diagrams': []
        }

        # List documents
        doc_dir = session_dir / 'document'
        if doc_dir.exists():
            for file_path in doc_dir.iterdir():
                if file_path.is_file():
                    result['documents'].append(self.get_file_info(file_path))

        # List diagrams
        diagram_dir = session_dir / 'diagram'
        if diagram_dir.exists():
            for file_path in diagram_dir.iterdir():
                if file_path.is_file():
                    result['diagrams'].append(self.get_file_info(file_path))

        return result

    def clear_session_files(self, session_id: str) -> bool:
        """
        Clear all files for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        try:
            session_dir = self.get_session_dir(session_id)
            if session_dir.exists():
                shutil.rmtree(session_dir)
            return True
        except Exception as e:
            print(f"Error clearing session files: {e}")
            return False

    def cleanup_old_sessions(self, days_old: int = 7) -> int:
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
            for session_dir in self.base_upload_dir.iterdir():
                if session_dir.is_dir():
                    # Check modification time
                    mtime = session_dir.stat().st_mtime
                    if mtime < cutoff_time:
                        shutil.rmtree(session_dir)
                        count += 1
        except Exception as e:
            print(f"Error during cleanup: {e}")

        return count
