"""
Embedding service for the Telegram RAG PDF Chatbot.
Creates and caches embedding model instances.
Mirrors the existing TS backend which uses OpenAI text-embedding-3-small.
"""

import time
from typing import List
import random
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger


class RobustGoogleEmbeddings(Embeddings):
    """
    A robust embeddings wrapper that implements sequential key rotation and automatic retry
    when an API call fails (e.g. rate limit, invalid key, or network timeout).
    """
    def __init__(self, model: str, api_keys: List[str]):
        self.model = model
        self.api_keys = api_keys if api_keys else [config.google_api_key]
        self.current_key_idx = 0

    def _get_embeddings_instance(self, key: str) -> GoogleGenerativeAIEmbeddings:
        return GoogleGenerativeAIEmbeddings(
            model=self.model,
            google_api_key=key,
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        last_error = None
        for attempt in range(len(self.api_keys)):
            idx = (self.current_key_idx + attempt) % len(self.api_keys)
            key = self.api_keys[idx]
            
            try:
                # Mask key for secure logging
                masked_key = key[:6] + "..." + key[-4:] if key else "None"
                logger.info(f"Attempting document embedding with key index {idx} ({masked_key})")
                
                embeddings_model = self._get_embeddings_instance(key)
                result = embeddings_model.embed_documents(texts)
                
                # Success! Save this key index as the starting point for future requests
                self.current_key_idx = idx
                return result
            except Exception as e:
                masked_key = key[:6] + "..." + key[-4:] if key else "None"
                logger.warning(
                    f"Embedding attempt failed with key index {idx} ({masked_key}). "
                    f"Attempt {attempt + 1}/{len(self.api_keys)}. Error: {e}"
                )
                last_error = e
                time.sleep(0.5)
                
        logger.error("All Google API keys failed for document embedding.")
        raise last_error or RuntimeError("Embedding failed with all API keys.")

    def embed_query(self, text: str) -> List[float]:
        last_error = None
        for attempt in range(len(self.api_keys)):
            idx = (self.current_key_idx + attempt) % len(self.api_keys)
            key = self.api_keys[idx]
            
            try:
                # Mask key for secure logging
                masked_key = key[:6] + "..." + key[-4:] if key else "None"
                logger.info(f"Attempting query embedding with key index {idx} ({masked_key})")
                
                embeddings_model = self._get_embeddings_instance(key)
                result = embeddings_model.embed_query(text)
                
                # Success! Save this key index as the starting point for future requests
                self.current_key_idx = idx
                return result
            except Exception as e:
                masked_key = key[:6] + "..." + key[-4:] if key else "None"
                logger.warning(
                    f"Embedding attempt failed with key index {idx} ({masked_key}). "
                    f"Attempt {attempt + 1}/{len(self.api_keys)}. Error: {e}"
                )
                last_error = e
                time.sleep(0.5)
                
        logger.error("All Google API keys failed for query embedding.")
        raise last_error or RuntimeError("Embedding failed with all API keys.")


# Global singleton instance
_robust_embeddings_instance = None

def get_embeddings() -> Embeddings:
    """
    Get the robust embeddings model instance (singleton).
    """
    global _robust_embeddings_instance
    if _robust_embeddings_instance is None:
        _robust_embeddings_instance = RobustGoogleEmbeddings(
            model=config.embedding_model,
            api_keys=config.google_api_keys,
        )
    return _robust_embeddings_instance
