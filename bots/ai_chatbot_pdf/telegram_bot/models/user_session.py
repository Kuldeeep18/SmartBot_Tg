"""
User session model for the Telegram RAG PDF Chatbot.
In-memory session management for chat history and user state.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone

from telegram_bot.utils.logger import logger


@dataclass
class UserSession:
    """Represents a single user's session state."""

    telegram_user_id: int
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    uploaded_doc_ids: List[str] = field(default_factory=list)
    active_document_id: Optional[str] = None
    active_filename: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Convert session to dictionary for JSON serialization."""
        return {
            "telegram_user_id": self.telegram_user_id,
            "chat_history": self.chat_history,
            "uploaded_doc_ids": self.uploaded_doc_ids,
            "active_document_id": self.active_document_id,
            "active_filename": self.active_filename,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserSession":
        """Reconstruct UserSession from dictionary."""
        return cls(
            telegram_user_id=data["telegram_user_id"],
            chat_history=data.get("chat_history", []),
            uploaded_doc_ids=data.get("uploaded_doc_ids", []),
            active_document_id=data.get("active_document_id"),
            active_filename=data.get("active_filename"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_active=data.get("last_active", datetime.now(timezone.utc).isoformat()),
        )

    def add_message(self, role: str, content: str):
        """Add a message to chat history, keeping only the last 10 messages."""
        self.chat_history.append({"role": role, "content": content})
        self.chat_history = self.chat_history[-10:]
        self.last_active = datetime.now(timezone.utc).isoformat()

    def add_document(self, doc_id: str, filename: str):
        """Track an uploaded document ID and set it as active."""
        if doc_id not in self.uploaded_doc_ids:
            self.uploaded_doc_ids.append(doc_id)
        self.active_document_id = doc_id
        self.active_filename = filename
        self.last_active = datetime.now(timezone.utc).isoformat()

    def clear_history(self):
        """Clear chat history but keep uploaded documents."""
        self.chat_history.clear()
        self.last_active = datetime.now(timezone.utc).isoformat()

    def reset(self):
        """Full reset — clear everything."""
        self.chat_history.clear()
        self.uploaded_doc_ids.clear()
        self.active_document_id = None
        self.active_filename = None
        self.last_active = datetime.now(timezone.utc).isoformat()


class SessionManager:
    """
    Thread-safe in-memory session manager with file persistence.
    Keyed by telegram_user_id.
    """

    def __init__(self):
        self._sessions: Dict[int, UserSession] = {}
        self._lock = asyncio.Lock()
        
        # Path to session storage
        from pathlib import Path
        self._filepath = Path(__file__).resolve().parent.parent.parent / "storage" / "sessions.json"
        
        # Load existing sessions synchronously on startup
        self._load_sessions()

    def _load_sessions(self):
        """Load sessions from file synchronously on initialization."""
        import json
        try:
            if self._filepath.exists():
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id_str, session_data in data.items():
                        user_id = int(user_id_str)
                        self._sessions[user_id] = UserSession.from_dict(session_data)
                logger.info(f"Loaded {len(self._sessions)} sessions from {self._filepath}")
            else:
                logger.info("No existing sessions file found. Starting fresh.")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}", exc_info=True)

    async def get_session(self, user_id: int) -> UserSession:
        """Get or create a session for a user."""
        async with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession(telegram_user_id=user_id)
                logger.info(f"Created new session for user {user_id}")
            return self._sessions[user_id]

    async def save_session(self, user_id: int):
        """Save sessions to disk asynchronously."""
        async with self._lock:
            import json
            import aiofiles
            import os
            try:
                # Ensure the storage directory exists
                self._filepath.parent.mkdir(parents=True, exist_ok=True)
                
                # Serialize all sessions
                serialized = {str(k): v.to_dict() for k, v in self._sessions.items()}
                
                # Write to temp file first, then rename for atomic write
                temp_filepath = self._filepath.with_suffix(".tmp")
                async with aiofiles.open(temp_filepath, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(serialized, indent=2))
                
                # Replace the original file atomically
                if os.path.exists(self._filepath):
                    os.remove(self._filepath)
                os.rename(temp_filepath, self._filepath)
                logger.info(f"Saved session for user/chat {user_id} to {self._filepath}")
            except Exception as e:
                logger.error(f"Failed to save session for user {user_id}: {e}", exc_info=True)

    async def reset_session(self, user_id: int):
        """Reset a user's session (clear history, keep docs)."""
        async with self._lock:
            if user_id in self._sessions:
                self._sessions[user_id].clear_history()
                logger.info(f"Reset session for user {user_id}")
        await self.save_session(user_id)

    async def full_reset_session(self, user_id: int):
        """Fully reset a user's session."""
        async with self._lock:
            if user_id in self._sessions:
                self._sessions[user_id].reset()
                logger.info(f"Full reset session for user {user_id}")
        await self.save_session(user_id)

    async def get_active_user_count(self) -> int:
        """Get count of active sessions."""
        async with self._lock:
            return len(self._sessions)


# Singleton session manager
session_manager = SessionManager()
