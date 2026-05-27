"""
PDF processing service for the Telegram RAG PDF Chatbot.
Handles PDF parsing, chunking, and metadata attachment.
Includes standard PyPDF parsing and Gemini-based OCR fallback for scanned PDFs.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger


async def extract_text_via_gemini(file_path: Path, filename: str) -> List[str]:
    """
    Upload the PDF to Gemini to extract page-by-page text.
    Rotates through available google_api_keys if 429 (quota) or other errors occur.
    """
    from google import genai
    from pydantic import BaseModel
    from typing import List as PyList
    
    class PageContent(BaseModel):
        page_number: int
        text: str

    class ExtractedDocument(BaseModel):
        pages: PyList[PageContent]

    keys = config.google_api_keys
    last_error = None

    for idx, key in enumerate(keys):
        if not key:
            continue
        client = None
        uploaded_file = None
        try:
            masked_key = key[:6] + "..." + key[-4:]
            logger.info(f"Attempting Gemini OCR text extraction using key index {idx} ({masked_key})...")
            client = genai.Client(api_key=key)
            
            # Upload the file
            uploaded_file = client.files.upload(file=str(file_path))
            logger.info(f"File uploaded to Gemini successfully: {uploaded_file.name}")
            
            # Generate content
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    uploaded_file,
                    "Extract all text from this PDF document page-by-page. "
                    "For each page, capture the text exactly as written. "
                    "If there are tables or tabular data, format them as Markdown tables to preserve structure and column alignment. "
                    "Do not omit any text."
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ExtractedDocument,
                }
            )
            
            extracted_doc = ExtractedDocument.model_validate_json(response.text)
            logger.info(f"Gemini OCR successfully extracted {len(extracted_doc.pages)} pages using key index {idx}")
            
            # Sort pages to ensure they are in order
            sorted_pages = sorted(extracted_doc.pages, key=lambda p: p.page_number)
            return [page.text for page in sorted_pages]
            
        except Exception as e:
            logger.warning(f"Gemini OCR attempt failed with key index {idx}: {e}")
            last_error = e
        finally:
            if client and uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                    logger.info(f"Deleted uploaded file {uploaded_file.name} from Gemini storage")
                except Exception as del_err:
                    logger.warning(f"Failed to delete uploaded file {uploaded_file.name} from Gemini: {del_err}")
                    
    logger.error("All Gemini API keys failed to perform OCR text extraction.")
    raise last_error or ValueError(f"Failed to extract text from {filename} using all available API keys.")


def detects_tabular_data(text: str) -> bool:
    """
    Detect if the text contains tabular structure (tables).
    Looks for lines with multiple columns separated by spacing gaps or tabs.
    """
    if not text:
        return False
        
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return False
        
    tabular_lines = 0
    for line in lines:
        # Check for tab characters or multiple space-separated columns
        # Tabular lines usually have columns separated by 3 or more spaces.
        if "\t" in line or re.search(r"\s{3,}", line):
            # Check if there are multiple words/numbers separated by these gaps
            parts = [p for p in re.split(r"\s{3,}|\t", line) if p.strip()]
            if len(parts) >= 2:
                tabular_lines += 1
                
    ratio = tabular_lines / len(lines)
    logger.info(f"Tabular detection: {tabular_lines}/{len(lines)} lines ({ratio:.2%}) classified as tabular.")
    
    # If 10% or more of non-empty lines are tabular, classify the document as tabular
    return ratio >= 0.10


async def process_pdf(
    file_path: Path,
    telegram_user_id: int,
    filename: str,
    force_ocr: bool = False,
) -> List[Document]:
    """
    Process a PDF file: parse, chunk, and attach metadata.
    """
    document_id = str(uuid.uuid4())
    upload_timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"Processing PDF: {filename} (doc_id: {document_id}, force_ocr: {force_ocr})")

    # Step 1: Load PDF pages using PyPDFLoader
    raw_pages = []
    if not force_ocr:
        try:
            loader = PyPDFLoader(str(file_path))
            raw_pages = loader.load()
        except Exception as e:
            logger.warning(f"PyPDFLoader failed to parse PDF '{filename}': {e}")

    # Check if we extracted meaningful text
    total_char_count = sum(len(p.page_content.strip()) for p in raw_pages)
    
    # Run tabular detection on the extracted text
    full_text = "\n".join(p.page_content for p in raw_pages)
    is_tabular = detects_tabular_data(full_text)
    
    if force_ocr or total_char_count < 100 or is_tabular:
        if force_ocr:
            logger.info(f"Forcing Gemini OCR extraction for table parsing or user request: '{filename}'")
        elif is_tabular:
            logger.info(f"Tabular structure detected in '{filename}'. Rerouting to Gemini OCR for table formatting...")
        else:
            logger.info(f"PyPDFLoader extracted very little text ({total_char_count} chars). Attempting Gemini OCR fallback...")
        try:
            pages_text = await extract_text_via_gemini(file_path, filename)
            
            # Reconstruct raw_pages list
            raw_pages = []
            for i, text in enumerate(pages_text):
                raw_pages.append(Document(
                    page_content=text,
                    metadata={"page": i}
                ))
            logger.info(f"Gemini OCR successfully reconstructed {len(raw_pages)} pages for '{filename}'")
        except Exception as ocr_err:
            logger.error(f"Gemini OCR fallback failed: {ocr_err}")
            raise ValueError(
                f"Could not extract any text from '{filename}'. "
                "Please ensure the PDF is not password-protected and contains selectable text, "
                f"or that your Gemini API keys have sufficient quota. (Gemini error: {ocr_err})"
            ) from ocr_err

    if not raw_pages:
        raise ValueError(f"PDF '{filename}' contains no extractable text.")

    total_pages = len(raw_pages)
    logger.info(f"Loaded {total_pages} pages from '{filename}'")

    # Step 2: Chunk the documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunked_docs: List[Document] = []

    for page_doc in raw_pages:
        # Get the page number (PyPDFLoader uses 0-indexed 'page' key)
        page_number = page_doc.metadata.get("page", 0) + 1  # Convert to 1-indexed

        # Skip empty pages
        if not page_doc.page_content.strip():
            continue

        # Split this page into chunks
        page_chunks = text_splitter.split_documents([page_doc])

        for i, chunk in enumerate(page_chunks):
            # Attach rich metadata for retrieval filtering and citations
            chunk.metadata = {
                # User isolation
                "telegram_user_id": telegram_user_id,
                # Document identification
                "document_id": document_id,
                "filename": filename,
                # Citation support
                "page_number": page_number,
                "chunk_index": i,
                "total_pages": total_pages,
                # Timestamps
                "upload_timestamp": upload_timestamp,
                # Source tracking
                "source": filename,
            }
            chunked_docs.append(chunk)

    logger.info(
        f"Chunked '{filename}' into {len(chunked_docs)} chunks "
        f"(from {total_pages} pages, chunk_size={config.chunk_size})"
    )

    if not chunked_docs:
        raise ValueError(
            f"Could not extract any text from '{filename}'. "
            "Please ensure the PDF is not password-protected and contains selectable text (not scanned images)."
        )

    return chunked_docs


async def save_uploaded_pdf(
    file_bytes: bytes,
    telegram_user_id: int,
    filename: str,
) -> Path:
    """
    Save an uploaded PDF to the local filesystem.
    """
    # Create user-specific directory
    user_dir = config.upload_dir / str(telegram_user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Deduplicate filename if it already exists
    file_path = user_dir / filename
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = user_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Write the file
    file_path.write_bytes(file_bytes)
    logger.info(f"Saved PDF to: {file_path} ({len(file_bytes)} bytes)")

    return file_path
