"""
Telegram bot handler: PDF save processing (/save command).
Downloads the PDF, processes it through the RAG pipeline, and stores embeddings.
"""

from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.models.user_session import session_manager
from telegram_bot.services import pdf_processor, vector_store
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger

# Maximum file size: 20MB
MAX_FILE_SIZE = 20 * 1024 * 1024


async def save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /save command.
    Processes a PDF document if:
    1. The message itself contains a PDF document (e.g. caption /save).
    2. The message is a reply to another message containing a PDF document.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Case 1: Reply to a message with a document
    document = None
    file_name = "unknown.pdf"

    if update.message.reply_to_message and update.message.reply_to_message.document:
        document = update.message.reply_to_message.document
        file_name = document.file_name or "unknown.pdf"
    # Case 2: The message itself is a document (e.g. caption /save)
    elif update.message.document:
        document = update.message.document
        file_name = document.file_name or "unknown.pdf"

    if not document:
        await update.message.reply_text(
            "❌ *No document found to save.*\n\n"
            "To save a document to this chat, either:\n"
            "• Upload a PDF, MD, or TXT file with the caption `/save`\n"
            "• Reply `/save` to any document already in the chat",
            parse_mode="Markdown"
        )
        return

    # Validate file type
    allowed_extensions = {".pdf", ".md", ".txt"}
    file_ext = Path(file_name).suffix.lower()
    if file_ext not in allowed_extensions:
        await update.message.reply_text(
            "❌ Unsupported file type. Only `.pdf`, `.md`, and `.txt` files are supported."
        )
        return

    # Validate file size
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        size_mb = document.file_size / (1024 * 1024)
        await update.message.reply_text(
            f"❌ File is too large ({size_mb:.1f} MB). Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )
        return

    logger.info(f"PDF save request in chat {chat_id} from user {user.id} ({user.first_name}): {file_name}")

    # Send progress message
    progress_msg = await update.message.reply_text(
        f"📥 Downloading {file_name}..."
    )

    try:
        # Step 1: Download the file
        config.ensure_dirs()
        tg_file = await document.get_file()
        file_bytes = await tg_file.download_as_bytearray()

        # Step 2: Save locally
        file_path = await pdf_processor.save_uploaded_pdf(
            file_bytes=bytes(file_bytes),
            telegram_user_id=chat_id,
            filename=file_name,
        )

        # Step 3: Update progress
        await progress_msg.edit_text(
            f"📄 Processing {file_name}...\nAnalyzing layout and extracting text..."
        )

        # Step 4: Parse and chunk the PDF
        documents = await pdf_processor.process_pdf(
            file_path=file_path,
            telegram_user_id=chat_id,
            filename=file_name,
        )

        # Step 5: Update progress
        await progress_msg.edit_text(
            f"🧠 Embedding {file_name}...\n{len(documents)} chunks to process..."
        )

        # Step 6: Store in vector database
        doc_ids = await vector_store.add_documents(documents)

        # Step 7: Update user session for this chat room
        session = await session_manager.get_session(chat_id)
        if documents:
            doc_id = documents[0].metadata.get("document_id", "unknown")
            session.add_document(doc_id, file_name)
            await session_manager.save_session(chat_id)
            
            # Start background deletion task (10 minutes)
            from telegram_bot.handlers.permsave import delete_temp_document
            import asyncio
            asyncio.create_task(delete_temp_document(chat_id, doc_id, file_name))

        # Step 8: Success message
        total_pages = documents[0].metadata.get("total_pages", "?") if documents else "?"
        page_label = "Virtual Pages" if file_ext in {".md", ".txt"} else "Pages"
        await progress_msg.edit_text(
            f"✅ `{file_name}` saved successfully to this chat!\n\n"
            f"📊 Stats:\n"
            f"• {page_label}: {total_pages}\n"
            f"• Chunks: {len(documents)}\n"
            f"• Vectors stored: {len(doc_ids)}\n\n"
            f"💬 Active document set. Ask questions about it!\n\n"
            f"⏳ *Note:* This file is stored temporarily and will be deleted in **10 minutes** unless you save it using `/permanentSave`.",
            parse_mode="Markdown"
        )

        logger.info(
            f"PDF processed for chat {chat_id}: {file_name} -> "
            f"{len(documents)} chunks, {len(doc_ids)} vectors"
        )

    except ValueError as e:
        # Known errors (corrupt PDF, empty PDF, etc.)
        await progress_msg.edit_text(f"❌ {str(e)}")
        logger.warning(f"PDF processing error in chat {chat_id}: {e}")

    except Exception as e:
        await progress_msg.edit_text(
            f"❌ Failed to process {file_name}.\n"
            f"Error: {str(e)[:200]}\n\n"
            f"Please try again or upload a different PDF."
        )
        logger.error(f"Unexpected error processing PDF in chat {chat_id}: {e}", exc_info=True)
