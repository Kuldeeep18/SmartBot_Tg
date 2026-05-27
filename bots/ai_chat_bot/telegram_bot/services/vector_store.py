"""
Supabase Vector Store service for the Telegram RAG PDF Chatbot.
Connects to the same Supabase instance as the existing TypeScript backend.
Uses the same 'documents' table and 'match_documents' function.
"""

from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client, Client as SupabaseClient

from telegram_bot.services.embeddings import get_embeddings
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger

# Singleton instances
_supabase_client: Optional[SupabaseClient] = None
_vector_store: Optional[SupabaseVectorStore] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create the Supabase client (singleton)."""
    global _supabase_client

    if _supabase_client is None:
        if not config.supabase_url or not config.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables"
            )
        _supabase_client = create_client(
            config.supabase_url,
            config.supabase_service_role_key,
        )
        logger.info("Supabase client initialized")

    return _supabase_client


def get_vector_store() -> SupabaseVectorStore:
    """
    Get or create the Supabase vector store (singleton).

    Uses the same configuration as the existing TS backend:
    - Table: 'documents'
    - Query function: 'match_documents'
    """
    global _vector_store

    if _vector_store is None:
        client = get_supabase_client()
        embeddings = get_embeddings()

        _vector_store = SupabaseVectorStore(
            client=client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents",
        )
        logger.info("Supabase vector store initialized")

    return _vector_store


async def add_documents(documents: List[Document]) -> List[str]:
    """
    Add documents to the vector store.

    Args:
        documents: List of LangChain Document objects with metadata.

    Returns:
        List of document IDs.
    """
    store = get_vector_store()
    logger.info(f"Adding {len(documents)} document chunks to vector store")

    try:
        ids = await store.aadd_documents(documents)
        logger.info(f"Successfully added {len(ids)} chunks to vector store")
        return ids
    except Exception as e:
        logger.error(f"Error adding documents to vector store: {e}")
        raise


async def similarity_search(
    query: str,
    user_id: Optional[int] = None,
    document_id: Optional[str] = None,
    k: Optional[int] = None,
) -> List[Document]:
    """
    Perform similarity search on the vector store.

    Args:
        query: The search query.
        user_id: Optional Telegram user ID to filter by (user isolation).
        document_id: Optional Document ID to filter by.
        k: Number of results to return (defaults to config.retriever_k).

    Returns:
        List of matching Document objects.
    """
    store = get_vector_store()
    # Detect global/aggregation queries to dynamically expand the retrieval window (k) to 100
    import re
    global_keywords = {
        "all", "list", "below", "above", "average", "sum", "total", "count", 
        "every", "whose", "students", "marksheet", "overall", "summary", 
        "highest", "lowest", "max", "min", "top", "bottom"
    }
    is_global_query = any(re.search(rf"\b{re.escape(kw)}\b", query.lower()) for kw in global_keywords)
    
    if is_global_query:
        num_results = 100
        logger.info(f"Global/aggregation query detected. Expanding retrieval k to {num_results}.")
    else:
        num_results = k or config.retriever_k

    # Build filter for user/document isolation
    filter_kwargs: Dict[str, Any] = {}
    if user_id is not None:
        filter_kwargs["telegram_user_id"] = user_id
    if document_id is not None:
        filter_kwargs["document_id"] = document_id

    logger.info(
        f"Similarity search: query='{query[:50]}...', k={num_results}, "
        f"user_filter={'user_' + str(user_id) if user_id else 'none'}, "
        f"doc_filter={document_id or 'none'}"
    )

    vector_results = []
    try:
        vector_results = await store.asimilarity_search(
            query,
            k=num_results,
            filter=filter_kwargs if filter_kwargs else None,
        )
        logger.info(f"Found {len(vector_results)} vector-matching documents")
    except Exception as e:
        logger.error(f"Error during similarity search: {e}")
        # Continue to try keyword fallback even if vector search fails
        vector_results = []

    # Step 2: Extract query keywords for keyword matching (names, roll numbers, etc.)
    import re
    words = [w.strip("?,.!:;\"'()[]{}") for w in query.split()]
    stop_words = {
        "what", "is", "the", "of", "in", "and", "for", "to", "a", "an", "give", 
        "total", "marks", "find", "get", "show", "tell", "who", "where", "how", 
        "list", "check", "please", "me", "my", "our", "him", "her", "them", 
        "student", "roll", "number", "marksheet", "pdf", "file", "document", "ask"
    }
    keywords = [w.lower() for w in words if w.lower() not in stop_words and len(w) >= 3]
    
    hybrid_results = list(vector_results)
    
    if keywords:
        logger.info(f"Hybrid search: extracted search keywords: {keywords}")
        try:
            client = get_supabase_client()
            db_query = client.table("documents").select("content, metadata")
            
            if user_id is not None:
                db_query = db_query.eq("metadata->>telegram_user_id", str(user_id))
            if document_id is not None:
                db_query = db_query.eq("metadata->>document_id", document_id)
                
            response = db_query.execute()
            
            keyword_matches = []
            seen_contents = {res.page_content.strip() for res in vector_results}
            
            for row in response.data or []:
                content = row.get("content", "")
                metadata = row.get("metadata", {})
                
                content_lower = content.lower()
                matches_count = sum(1 for kw in keywords if kw in content_lower)
                
                if matches_count > 0:
                    if content.strip() in seen_contents:
                        continue
                        
                    # Calculate exact phrase match score (e.g. "goklani kuldeep" or "kuldeep goklani")
                    phrase_score = 0
                    if len(keywords) >= 2:
                        phrase_1 = " ".join(keywords)
                        phrase_2 = " ".join(reversed(keywords))
                        if phrase_1 in content_lower or phrase_2 in content_lower:
                            phrase_score = 10
                            
                    score = matches_count + phrase_score
                    
                    doc = Document(page_content=content, metadata=metadata)
                    keyword_matches.append((score, doc))
            
            # Sort by match score descending
            keyword_matches.sort(key=lambda x: x[0], reverse=True)
            
            # Prepend the top keyword-matched documents (up to 3) to the retrieved results
            added_count = 0
            for score, doc in keyword_matches:
                hybrid_results.insert(added_count, doc)
                added_count += 1
                logger.info(f"Hybrid search: prepended high-priority keyword match (score={score}): '{doc.page_content[:60]}...'")
                
                if added_count >= 3:
                    break
                    
            logger.info(f"Hybrid search completed: returned {len(hybrid_results)} documents (added {added_count} keyword matches)")
        except Exception as e:
            logger.error(f"Error during hybrid search: {e}", exc_info=True)
            
    return hybrid_results


async def get_user_document_count(user_id: int) -> int:
    """
    Get the count of document chunks for a specific user.

    Args:
        user_id: Telegram user ID.

    Returns:
        Number of document chunks belonging to the user.
    """
    try:
        client = get_supabase_client()
        result = (
            client.table("documents")
            .select("id", count="exact")
            .eq("metadata->>telegram_user_id", str(user_id))
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.error(f"Error getting document count for user {user_id}: {e}")
        return 0


async def get_user_documents_info(user_id: int) -> List[Dict[str, Any]]:
    """
    Get information about documents uploaded by a specific user.

    Args:
        user_id: Telegram user ID.

    Returns:
        List of dicts with document metadata (filename, upload_timestamp, etc).
    """
    try:
        client = get_supabase_client()
        result = (
            client.table("documents")
            .select("metadata")
            .eq("metadata->>telegram_user_id", str(user_id))
            .execute()
        )

        # Deduplicate by document_id to get unique files
        seen_docs = {}
        for row in result.data or []:
            meta = row.get("metadata", {})
            doc_id = meta.get("document_id", "unknown")
            if doc_id not in seen_docs:
                seen_docs[doc_id] = {
                    "filename": meta.get("filename", "Unknown"),
                    "document_id": doc_id,
                    "upload_timestamp": meta.get("upload_timestamp", "Unknown"),
                    "total_pages": meta.get("total_pages", "?"),
                }

        return list(seen_docs.values())
    except Exception as e:
        logger.error(f"Error getting documents info for user {user_id}: {e}")
        return []
