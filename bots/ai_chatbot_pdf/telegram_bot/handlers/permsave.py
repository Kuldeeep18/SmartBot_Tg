"""
Telegram bot handler: /permanentSave.
Manages permanent documents limit (max 3), inline keyboard replacement,
and 10-minute temporary file deletion with startup cleanup recovery.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application

from telegram_bot.models.user_session import session_manager
from telegram_bot.services import vector_store, pdf_processor
from telegram_bot.utils.logger import logger
from telegram_bot.utils.decorators import enforce_group_tag

# Deletion delay: 10 minutes (600 seconds)
DELETION_DELAY_SECONDS = 600.0


async def delete_temp_document(chat_id: int, doc_id: str, filename: str, delay: float = DELETION_DELAY_SECONDS):
    """
    Background task to delete a temporary document after a delay.
    If the document has been marked permanent, the deletion is skipped.
    """
    logger.info(f"Scheduled deletion for temp document {doc_id} ({filename}) in chat {chat_id} in {delay:.1f}s")
    await asyncio.sleep(delay)

    try:
        session = await session_manager.get_session(chat_id)
        
        # Check if the document was saved permanently in the meantime
        if doc_id in session.permanent_doc_ids:
            logger.info(f"Temp document {doc_id} was saved permanently. Deletion canceled.")
            return

        logger.info(f"Deleting expired temporary document {doc_id} ({filename}) in chat {chat_id}")
        
        # 1. Delete chunks from Supabase
        await vector_store.delete_document(chat_id, doc_id)
        
        # 2. Delete local PDF file
        pdf_processor.delete_local_pdf(chat_id, filename)

        # 3. Clean up user session
        if doc_id in session.uploaded_doc_ids:
            session.uploaded_doc_ids.remove(doc_id)
        if doc_id in session.temp_docs:
            session.temp_docs.pop(doc_id)
        if session.active_document_id == doc_id:
            session.active_document_id = None
            session.active_filename = None

        await session_manager.save_session(chat_id)
        logger.info(f"Successfully cleaned up expired temp document {doc_id} ({filename})")
        
    except Exception as e:
        logger.error(f"Error during temporary document cleanup {doc_id}: {e}", exc_info=True)


@enforce_group_tag
async def permsave_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /permanentSave command.
    Saves the active/last-uploaded document permanently.
    Limits permanent files to 3 per chat session.
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    logger.info(f"/permanentSave in chat {chat_id} from user {user.id} ({user.first_name})")

    session = await session_manager.get_session(chat_id)
    active_id = session.active_document_id
    active_name = session.active_filename

    if not active_id or not active_name:
        await update.message.reply_text(
            "❌ *No active document found.*\n\n"
            "Please upload a PDF document and use `/save` first before saving it permanently.",
            parse_mode="Markdown"
        )
        return

    # Case 1: Document is already permanent
    if active_id in session.permanent_doc_ids:
        await update.message.reply_text(
            f"ℹ️ The document `{active_name}` is already saved permanently!\n"
            f"Slots used: {len(session.permanent_doc_ids)}/3"
        )
        return

    # Case 2: Slots available (< 3)
    if len(session.permanent_doc_ids) < 3:
        session.permanent_doc_ids.append(active_id)
        # Remove from temp docs tracking if present
        if active_id in session.temp_docs:
            session.temp_docs.pop(active_id)
        
        await session_manager.save_session(chat_id)
        
        await update.message.reply_text(
            f"✅ *Document Saved Permanently!*\n\n"
            f"📄 File: `{active_name}`\n"
            f"📦 Slots used: {len(session.permanent_doc_ids)}/3\n\n"
            f"This file will not be deleted automatically.",
            parse_mode="Markdown"
        )
        return

    # Case 3: Limit reached (>= 3), require replacement selection
    # Fetch filenames for all 3 permanent docs
    keyboard = []
    try:
        docs_info = await vector_store.get_user_documents_info(chat_id)
        permanent_docs = [d for d in docs_info if d.get("document_id") in session.permanent_doc_ids]
        
        for doc in permanent_docs:
            filename = doc.get("filename", "Unknown")
            doc_id = doc.get("document_id", "")
            # Callback data: permsave_replace:<old_id>:<new_id>
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ Remove: {filename}",
                    callback_data=f"permsave_replace:{doc_id}:{active_id}"
                )
            ])
    except Exception as e:
        logger.error(f"Error fetching filenames for slot selection: {e}")
        # Fallback to listing IDs
        for doc_id in session.permanent_doc_ids:
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ Remove: {doc_id[:8]}...",
                    callback_data=f"permsave_replace:{doc_id}:{active_id}"
                )
            ])

    keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="permsave_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⚠️ *Storage Slot Limit Reached (3/3)*\n\n"
        f"You want to save: `{active_name}`\n\n"
        f"Please select one of your 3 permanent files to **remove and overwrite** below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def permsave_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle inline buttons for /permanentSave slot replacement.
    """
    query = update.callback_query
    chat_id = query.message.chat.id
    user = query.from_user
    
    await query.answer()

    session = await session_manager.get_session(chat_id)
    data = query.data

    if data == "permsave_cancel":
        await query.edit_message_text(
            "❌ *Permanent save cancelled.*\n\n"
            "The active document will remain temporary and will be deleted in 10 minutes from its upload time.",
            parse_mode="Markdown"
        )
        return

    if data.startswith("permsave_replace:"):
        parts = data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ Invalid callback data.")
            return

        old_doc_id = parts[1]
        new_doc_id = parts[2]

        # Resolve filenames for feedback
        old_filename = await vector_store.get_document_filename(chat_id, old_doc_id) or "Old Document"
        new_filename = await vector_store.get_document_filename(chat_id, new_doc_id) or "New Document"

        logger.info(f"Replacing permanent doc {old_doc_id} with {new_doc_id} in chat {chat_id}")

        try:
            # 1. Delete the old document from Supabase
            await vector_store.delete_document(chat_id, old_doc_id)

            # 2. Delete the old document locally
            pdf_processor.delete_local_pdf(chat_id, old_filename)

            # 3. Clean up the session references
            if old_doc_id in session.permanent_doc_ids:
                session.permanent_doc_ids.remove(old_doc_id)
            if old_doc_id in session.uploaded_doc_ids:
                session.uploaded_doc_ids.remove(old_doc_id)

            # 4. Add the new document to permanent list
            session.permanent_doc_ids.append(new_doc_id)
            if new_doc_id in session.temp_docs:
                session.temp_docs.pop(new_doc_id)

            await session_manager.save_session(chat_id)

            await query.edit_message_text(
                f"🔄 *Storage Slots Updated Successfully!*\n\n"
                f"🗑️ Removed: `{old_filename}`\n"
                f"💾 Saved: `{new_filename}` permanently.\n"
                f"📦 Slots used: {len(session.permanent_doc_ids)}/3",
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Error executing document slot swap in chat {chat_id}: {e}", exc_info=True)
            await query.edit_message_text("❌ Failed to swap documents due to an error. Please try again.")


async def initialize_startup_cleanup(application: Application):
    """
    On bot startup, scan all user sessions and resume/cleanup deletion tasks:
    1. Instantly delete temporary documents older than 10 minutes.
    2. Reschedule deletion for documents uploaded less than 10 minutes ago.
    """
    logger.info("Initializing startup temporary document cleanup scan...")
    now = datetime.now(timezone.utc)
    
    # We retrieve the sessions dictionary directly from the session manager
    sessions = session_manager._sessions
    
    for chat_id, session in list(sessions.items()):
        temp_docs_list = list(session.temp_docs.items())
        for doc_id, doc_info in temp_docs_list:
            # Skip if somehow marked permanent in session
            if doc_id in session.permanent_doc_ids:
                session.temp_docs.pop(doc_id, None)
                continue
                
            filename = doc_info.get("filename", "unknown.pdf")
            uploaded_at_str = doc_info.get("uploaded_at")
            
            if not uploaded_at_str:
                # If no timestamp, safely clean it up
                asyncio.create_task(delete_temp_document(chat_id, doc_id, filename, delay=0.0))
                continue
                
            try:
                uploaded_at = datetime.fromisoformat(uploaded_at_str)
                time_passed = (now - uploaded_at).total_seconds()
                
                if time_passed >= DELETION_DELAY_SECONDS:
                    # Already expired, delete immediately
                    logger.info(f"Startup cleanup: Document {doc_id} expired {time_passed - DELETION_DELAY_SECONDS:.1f}s ago. Deleting now.")
                    asyncio.create_task(delete_temp_document(chat_id, doc_id, filename, delay=0.0))
                else:
                    # Still active, reschedule with remaining time
                    remaining = DELETION_DELAY_SECONDS - time_passed
                    logger.info(f"Startup cleanup: Rescheduling deletion for {doc_id} in {remaining:.1f}s.")
                    asyncio.create_task(delete_temp_document(chat_id, doc_id, filename, delay=remaining))
            except Exception as parse_err:
                logger.error(f"Failed to parse timestamp for {doc_id} on startup cleanup: {parse_err}")
                asyncio.create_task(delete_temp_document(chat_id, doc_id, filename, delay=0.0))
