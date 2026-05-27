"""
RAG Chain service for the Telegram RAG PDF Chatbot.
Mirrors the existing TypeScript retrieval graph logic with enhanced
multi-provider fallback, key rotation, and response verification.
"""

from typing import Optional, List, Dict, Any
import random
import time

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from telegram_bot.services import vector_store
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger

# ──────────────────────────────────────────────────────────────
# Prompts — matching existing TS prompts.ts
# ──────────────────────────────────────────────────────────────

# Mirrors ROUTER_SYSTEM_PROMPT from retrieval_graph/prompts.ts
ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a routing assistant. Your job is to determine if a question needs document retrieval or can be answered directly.\n\n"
        "Respond with ONLY one word:\n"
        "'retrieve' - if the question is about uploaded documents, PDFs, or specific content the user may have shared\n"
        "'direct' - if the question is general knowledge and can be answered directly\n\n"
        "Respond with just the single word: retrieve or direct",
    ),
    ("human", "{query}"),
])

# Enhanced version of RESPONSE_SYSTEM_PROMPT from retrieval_graph/prompts.ts
# Adds citation support (page numbers and source snippets)
RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful assistant for question-answering tasks. Use the following pieces of retrieved context and conversation history to answer the question.\n\n"
        "RULES:\n"
        "1. Answer based on the provided context. If the context doesn't contain the answer, say so clearly.\n"
        "2. Keep answers concise but thorough.\n"
        "3. ALWAYS cite your sources by mentioning the page number and filename when available.\n"
        "   Format citations like: 'According to page X of [filename]...'\n"
        "4. If multiple sources support your answer, reference all of them.\n"
        "5. Do not make up information that isn't in the context."
    ),
    (
        "human",
        "Conversation History:\n{chat_history}\n\nQuestion:\n{question}\n\nContext:\n{context}"
    ),
])

DIRECT_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful AI assistant. Answer the user's question directly and concisely, utilizing the conversation history when relevant.",
    ),
    (
        "human",
        "Conversation History:\n{chat_history}\n\nQuestion:\n{query}"
    ),
])

# Prompt for answer verification (consensus checking)
VERIFY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an answer verification assistant. Your job is to check if a generated answer is accurate, "
        "coherent, and fully supported by the provided context. If the answer is helpful and matches the context, reply with 'VALID'. "
        "If the answer states that the context doesn't contain the answer (e.g., 'I cannot find...', 'The context doesn't mention...'), "
        "and this is indeed true (the context has no info), reply with 'VALID'. "
        "If the answer is incorrect, contains hallucinated facts not in the context, is blank, or indicates an error, reply with 'INVALID'.\n\n"
        "Respond with ONLY one word: VALID or INVALID."
    ),
    (
        "human",
        "Context:\n{context}\n\nQuestion:\n{question}\n\nGenerated Answer:\n{answer}"
    ),
])

# ──────────────────────────────────────────────────────────────
# Multi-LLM Service Fallbacks & Factory
# ──────────────────────────────────────────────────────────────

def get_active_providers(primary_provider: str) -> List[Dict[str, Any]]:
    """
    Assemble the list of available providers based on configured API keys in .env.
    Puts the selected primary_provider at the front of the list.
    """
    providers = []

    # 1. Groq
    if config.groq_api_key:
        providers.append({
            "name": "groq",
            "model": config.llm_model if config.llm_provider == "groq" else "llama-3.3-70b-versatile",
            "keys": [config.groq_api_key],
        })

    # 2. NVIDIA
    if config.nvidia_api_key:
        providers.append({
            "name": "nvidia",
            "model": "meta/llama-3.1-70b-instruct",
            "keys": [config.nvidia_api_key],
        })

    # 3. G0I
    if config.g0i_api_key:
        providers.append({
            "name": "g0i",
            "model": config.llm_model if config.llm_provider == "g0i" else "gpt-5.5",
            "keys": [config.g0i_api_key],
        })

    # 4. OpenRouter
    if config.openrouter_api_key:
        providers.append({
            "name": "openrouter",
            "model": config.llm_model if config.llm_provider == "openrouter" else "openai/gpt-4o-mini",
            "keys": [config.openrouter_api_key],
        })

    # 5. OpenAI
    if config.openai_api_key and "YOUR_OPENAI" not in config.openai_api_key:
        providers.append({
            "name": "openai",
            "model": config.llm_model if config.llm_provider == "openai" else "gpt-4o-mini",
            "keys": [config.openai_api_key],
        })

    # Rearrange so primary provider is tried first
    primary_lower = primary_provider.lower()
    primary_item = None
    for p in providers:
        if p["name"] == primary_lower:
            primary_item = p
            break

    if primary_item:
        providers.remove(primary_item)
        providers.insert(0, primary_item)

    return providers


def create_model(provider_info: Dict[str, Any], api_key: str, temperature: float = 0.2):
    """
    Instantiate the appropriate LangChain chat model wrapper.
    """
    name = provider_info["name"]
    model_name = provider_info["model"]

    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key,
        )
    elif name == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=api_key,
        )
    elif name == "nvidia":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://integrate.api.nvidia.com/v1",
        )
    elif name == "g0i":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://g0i.ai/v1",
        )
    elif name == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
        )
    elif name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {name}")


async def invoke_chain_with_fallback(
    prompt: ChatPromptTemplate,
    input_variables: Dict[str, Any],
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    Invoke an LLM chain, trying all configured keys and providers sequentially
    until a successful response is received.
    """
    providers = get_active_providers(config.llm_provider)
    if not providers:
        raise ValueError("No active LLM providers configured in .env")

    last_error = None
    for p in providers:
        for idx, key in enumerate(p["keys"]):
            if not key:
                continue
            try:
                masked_key = key[:6] + "..." + key[-4:] if key else "None"
                logger.info(
                    f"Trying LLM execution with provider='{p['name']}', model='{p['model']}', "
                    f"key index {idx} ({masked_key})"
                )
                model = create_model(p, key, temperature)
                chain = prompt | model | StrOutputParser()
                result = await chain.ainvoke(input_variables)
                return {
                    "result": result,
                    "provider": p["name"],
                    "model": p["model"],
                }
            except Exception as e:
                logger.warning(
                    f"LLM execution failed for provider='{p['name']}' with key index {idx}. Error: {e}"
                )
                last_error = e
                time.sleep(0.5)

    raise last_error or RuntimeError("All LLM providers and keys failed to invoke.")


async def verify_answer(
    question: str,
    context: str,
    answer: str,
    generator_provider: str
) -> bool:
    """
    Use an independent fallback model (consensus check) to verify if the generated answer is valid.
    """
    providers = get_active_providers(config.llm_provider)
    
    # Try to find a different verifier provider for consensus check
    verifier_provider = None
    for p in providers:
        if p["name"] != generator_provider:
            verifier_provider = p
            break

    # Fall back to any provider (even same) if only one is configured
    if not verifier_provider and providers:
        verifier_provider = providers[0]

    if not verifier_provider:
        logger.warning("No verifier provider available. Skipping answer verification.")
        return True

    for idx, key in enumerate(verifier_provider["keys"]):
        if not key:
            continue
        try:
            logger.info(
                f"Verifying response quality using provider='{verifier_provider['name']}' "
                f"({verifier_provider['model']}) via key index {idx}"
            )
            model = create_model(verifier_provider, key, temperature=0.0)
            chain = VERIFY_PROMPT | model | StrOutputParser()
            
            result = await chain.ainvoke({
                "context": context,
                "question": question,
                "answer": answer,
            })
            validation = result.strip().upper()
            logger.info(f"Verification validation output: '{validation}'")
            return "VALID" in validation
        except Exception as e:
            logger.warning(
                f"Verification failed using provider='{verifier_provider['name']}' "
                f"key index {idx}: {e}"
            )

    # If verification fails to execute, don't discard the answer
    return True


# ──────────────────────────────────────────────────────────────
# Document Formatting — mirrors retrieval_graph/utils.ts
# ──────────────────────────────────────────────────────────────

def _format_doc(doc: Document) -> str:
    """
    Format a single document as XML with metadata.
    Mirrors formatDoc() from retrieval_graph/utils.ts
    """
    metadata = doc.metadata or {}
    meta_parts = []
    for key in ["filename", "page_number", "source"]:
        if key in metadata:
            meta_parts.append(f'{key}="{metadata[key]}"')

    meta_str = " " + " ".join(meta_parts) if meta_parts else ""
    return f"<document{meta_str}>\n{doc.page_content}\n</document>"


def _format_docs(docs: List[Document]) -> str:
    """
    Format a list of documents as XML.
    Mirrors formatDocs() from retrieval_graph/utils.ts
    """
    if not docs:
        return "<documents></documents>"
    formatted = "\n".join(_format_doc(doc) for doc in docs)
    return f"<documents>\n{formatted}\n</documents>"


def _format_citations(docs: List[Document]) -> str:
    """
    Build a citations section from retrieved documents.
    """
    if not docs:
        return ""

    citations = []
    seen = set()

    for doc in docs:
        meta = doc.metadata or {}
        filename = meta.get("filename", "Unknown")
        page = meta.get("page_number", "?")
        key = f"{filename}:p{page}"

        if key not in seen:
            seen.add(key)
            snippet = doc.page_content[:100].replace("\n", " ").strip()
            citations.append(f"📄 {filename}, page {page}: \"{snippet}...\"")

    if citations:
        return "\n\n📚 **Sources:**\n" + "\n".join(citations)
    return ""


# ──────────────────────────────────────────────────────────────
# Main RAG Pipeline
# ──────────────────────────────────────────────────────────────

async def check_query_type(query: str) -> str:
    """
    Route the query: does it need document retrieval or a direct answer?
    Mirrors checkQueryType() from retrieval_graph/graph.ts
    """
    try:
        res = await invoke_chain_with_fallback(ROUTER_PROMPT, {"query": query}, temperature=0.0)
        route = res["result"].strip().lower()

        if route in ("retrieve", "direct"):
            logger.info(f"Query routed as: {route} (via provider '{res['provider']}')")
            return route
        else:
            logger.warning(f"Unclear routing result '{route}', defaulting to 'retrieve'")
            return "retrieve"
    except Exception as e:
        logger.error(f"Error in query routing: {e}")
        return "retrieve"  # Safe default


async def answer_query(
    query: str,
    telegram_user_id: int,
    chat_history: Optional[List[Dict[str, str]]] = None,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point: answer a user's question using the RAG pipeline.
    """
    # Format the last 10 messages of chat history as a log string
    history_str = "No previous history."
    if chat_history:
        recent_history = chat_history[-10:]
        history_parts = []
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_parts.append(f"{role}: {msg['content']}")
        history_str = "\n".join(history_parts)

    # Step 1: Route the query
    route = await check_query_type(query)

    if route == "direct":
        try:
            res = await invoke_chain_with_fallback(
                DIRECT_ANSWER_PROMPT,
                {"query": query, "chat_history": history_str}
            )
            return {
                "answer": res["result"],
                "sources": [],
                "route": "direct",
            }
        except Exception as e:
            logger.error(f"Failed to generate direct answer: {e}")
            return {
                "answer": "Sorry, I encountered an issue answering your question directly. Please try again.",
                "sources": [],
                "route": "direct",
            }

    # Step 2: Retrieve documents
    documents = await vector_store.similarity_search(
        query=query,
        user_id=telegram_user_id,
        document_id=document_id,
        k=config.retriever_k,
    )

    if not documents:
        return {
            "answer": (
                "I couldn't find any relevant information in your uploaded documents. "
                "Please make sure you've uploaded a PDF first, or try rephrasing your question."
            ),
            "sources": [],
            "route": "retrieve",
        }

    # Step 3: Generate response and verify
    context = _format_docs(documents)
    providers = get_active_providers(config.llm_provider)

    last_error = None
    fallback_answers = []

    for p in providers:
        for idx, key in enumerate(p["keys"]):
            if not key:
                continue
            try:
                logger.info(
                    f"Attempting response generation with provider='{p['name']}', "
                    f"model='{p['model']}', key index {idx}"
                )
                model = create_model(p, key, temperature=0.2)
                chain = RESPONSE_PROMPT | model | StrOutputParser()
                
                answer = await chain.ainvoke({
                    "question": query,
                    "context": context,
                    "chat_history": history_str,
                })
                
                # Check consensus validation
                is_valid = await verify_answer(query, context, answer, generator_provider=p["name"])
                
                citations = _format_citations(documents)
                full_answer = answer + citations

                if is_valid:
                    logger.info(f"Response successfully verified using provider='{p['name']}'")
                    return {
                        "answer": full_answer,
                        "sources": documents,
                        "route": "retrieve",
                    }
                else:
                    logger.warning(
                        f"Response from provider='{p['name']}' failed validation. "
                        f"Saving as fallback and trying next provider..."
                    )
                    fallback_answers.append(full_answer)
            except Exception as e:
                logger.warning(
                    f"Response generation failed with provider='{p['name']}' key index {idx}: {e}"
                )
                last_error = e
                time.sleep(0.5)

    # If all generators failed or returned invalid responses, return the first fallback answer or raise error
    if fallback_answers:
        logger.warning("All verification checks failed. Returning the first generated response as fallback.")
        return {
            "answer": fallback_answers[0],
            "sources": documents,
            "route": "retrieve",
        }

    if last_error:
        raise last_error

    return {
        "answer": "Sorry, I could not generate a response using the available API keys. Please try again later.",
        "sources": [],
        "route": "retrieve",
    }
