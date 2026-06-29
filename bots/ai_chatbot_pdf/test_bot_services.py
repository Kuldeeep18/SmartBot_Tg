import asyncio
import logging
from pathlib import Path

# Setup logging before imports to catch their logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TestSuite")

from telegram_bot.services import pdf_processor, vector_store, rag_chain
from telegram_bot.utils.config import config

# We will use a dummy user ID for testing
TEST_USER_ID = 999999
TEST_PDF_PATH = Path("telegram_bot/test_docs/test-tsla-10k-2023.pdf").resolve()

async def test_pdf_parsing():
    logger.info("=== TEST 1: PDF Parsing ===")
    if not TEST_PDF_PATH.exists():
        logger.error(f"Test PDF not found at {TEST_PDF_PATH}")
        return None
    
    docs = await pdf_processor.process_pdf(
        file_path=TEST_PDF_PATH,
        telegram_user_id=TEST_USER_ID,
        filename=TEST_PDF_PATH.name
    )
    logger.info(f"Successfully processed PDF into {len(docs)} chunks.")
    assert len(docs) > 0, "No documents were parsed."
    
    first_doc = docs[0]
    logger.info(f"Metadata of first chunk: {first_doc.metadata}")
    assert first_doc.metadata.get("telegram_user_id") == TEST_USER_ID, "User ID not attached correctly."
    return docs

async def test_vector_store(docs):
    logger.info("=== TEST 2: Vector Store Ingestion and Search ===")
    # Add a subset to avoid eating too many OpenAI tokens and time
    # Just the first 10 chunks
    subset = docs[:10]
    logger.info(f"Adding {len(subset)} chunks to vector store...")
    
    doc_ids = await vector_store.add_documents(subset)
    logger.info(f"Successfully added. IDs: {doc_ids[:3]}...")
    assert len(doc_ids) == len(subset), "Mismatch in added documents count."

    # Test search
    query = "What is Tesla's business?"
    logger.info(f"Searching for: '{query}'")
    results = await vector_store.similarity_search(query=query, user_id=TEST_USER_ID, k=2)
    logger.info(f"Search returned {len(results)} results.")
    for i, res in enumerate(results):
        logger.info(f"Result {i+1} snippet: {res.page_content[:100]}...")

    # Test user count
    count = await vector_store.get_user_document_count(TEST_USER_ID)
    logger.info(f"User {TEST_USER_ID} has {count} documents.")
    assert count >= len(subset), "User document count doesn't match."

async def test_rag_chain():
    logger.info("=== TEST 3: RAG Chain Generation ===")
    query = "Summarize Tesla's business based on the documents."
    logger.info(f"Asking RAG: '{query}'")
    
    result = await rag_chain.answer_query(
        query=query,
        telegram_user_id=TEST_USER_ID,
        chat_history=[]
    )
    
    logger.info(f"RAG Route: {result['route']}")
    logger.info(f"RAG Answer:\n{result['answer']}")
    logger.info(f"RAG Sources: {len(result['sources'])} sources used.")
    
async def run_all():
    try:
        # Load env vars
        errors = config.validate()
        if errors:
            logger.error("Configuration errors:")
            for e in errors:
                logger.error(e)
            return

        docs = await test_pdf_parsing()
        if docs:
            await test_vector_store(docs)
            await test_rag_chain()
        
        logger.info("=== ALL TESTS COMPLETED SUCCESSFULLY ===")
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_all())
