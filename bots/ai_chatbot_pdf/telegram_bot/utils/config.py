"""
Configuration loader for the Telegram RAG PDF Chatbot.
Loads environment variables and provides typed access to all config values.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


@dataclass
class Config:
    """Central configuration loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    # LLM
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))

    # API Keys
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    nvidia_api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""))
    g0i_api_key: str = field(default_factory=lambda: os.getenv("G0I_API_KEY", ""))

    # RAG
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1000")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "200")))
    retriever_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVER_K", "5")))

    # Paths
    upload_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "storage" / "uploaded_pdfs")

    @property
    def google_api_keys(self) -> list[str]:
        """Returns a list of Google API keys from GOOGLE_API_KEYS or fallback to GOOGLE_API_KEY"""
        keys_str = os.getenv("GOOGLE_API_KEYS", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not keys and self.google_api_key:
            keys = [self.google_api_key]
        return keys

    def validate(self) -> list[str]:
        """Validate required configuration. Returns list of error messages."""
        errors = []
        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if not self.supabase_url:
            errors.append("SUPABASE_URL is required")
        if not self.supabase_service_role_key:
            errors.append("SUPABASE_SERVICE_ROLE_KEY is required")

        # Check that at least one LLM API key is set
        provider_key_map = {
            "openai": self.openai_api_key,
            "gemini": self.google_api_key or (self.google_api_keys[0] if self.google_api_keys else ""),
            "groq": self.groq_api_key,
            "openrouter": self.openrouter_api_key,
            "nvidia": self.nvidia_api_key,
            "g0i": self.g0i_api_key,
        }
        key = provider_key_map.get(self.llm_provider, "")
        if not key:
            errors.append(f"API key for LLM_PROVIDER='{self.llm_provider}' is not set")

        return errors

    def ensure_dirs(self):
        """Create required directories if they don't exist."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)


# Singleton config instance
config = Config()
