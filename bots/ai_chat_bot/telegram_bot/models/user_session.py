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

    def add_message(self, role: str, content: str):
        """Add a message to chat history."""
        self.chat_history.append({"role": role, "content": content})
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
    Thread-safe in-memory session manager.
    Keyed by telegram_user_id.
    """

    def __init__(self):
        self._sessions: Dict[int, UserSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, user_id: int) -> UserSession:
        """Get or create a session for a user."""
        async with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession(telegram_user_id=user_id)
                logger.info(f"Created new session for user {user_id}")
            return self._sessions[user_id]

    async def reset_session(self, user_id: int):
        """Reset a user's session (clear history, keep docs)."""
        async with self._lock:
            if user_id in self._sessions:
                self._sessions[user_id].clear_history()
                logger.info(f"Reset session for user {user_id}")

    async def full_reset_session(self, user_id: int):
        """Fully reset a user's session."""
        async with self._lock:
            if user_id in self._sessions:
                self._sessions[user_id].reset()
                logger.info(f"Full reset session for user {user_id}")

    async def get_active_user_count(self) -> int:
        """Get count of active sessions."""
        async with self._lock:
            return len(self._sessions)


# Singleton session manager
session_manager = SessionManager()
