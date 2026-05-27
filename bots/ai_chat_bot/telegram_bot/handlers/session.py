"""
Telegram bot handlers: session management commands (/reset, /mydocs, /status, /select).
Identifies sessions and document scopes by chat_id to support group chats correctly.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from telegram_bot.models.user_session import session_manager
from telegram_bot.services import vector_store
from telegram_bot.utils.logger import logger


async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /reset command.
    Clears the chat history for this chat, preserving uploaded documents.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"/reset in chat {chat_id} from user {user.id} ({user.first_name})")

    await session_manager.reset_session(chat_id)

    await update.message.reply_text(
        "🔄 Chat history for this chat has been cleared!\n\n"
        "Your saved documents are still available. "
        "Feel free to ask new questions about them."
    )


async def mydocs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /mydocs command.
    Lists all PDFs saved in this chat.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"/mydocs in chat {chat_id} from user {user.id} ({user.first_name})")

    await update.message.reply_text("🔍 Looking up saved documents...")

    try:
        docs_info = await vector_store.get_user_documents_info(chat_id)

        if not docs_info:
            await update.message.reply_text(
                "📭 No documents saved in this chat yet.\n\n"
                "Save a PDF file using the `/save` command!"
            )
            return

        session = await session_manager.get_session(chat_id)
        active_id = session.active_document_id

        # Build the document list
        lines = [f"📚 **Saved Documents** ({len(docs_info)} files):\n"]
        
        # Add Search All status if active_id is None
        if active_id is None:
            lines.append("🔍 *Search Mode:* All Documents (🟢 Active)\n")
        else:
            lines.append(f"🔍 *Search Mode:* Single Document (Active: `{session.active_filename}`)\n")

        for i, doc in enumerate(docs_info, 1):
            filename = doc.get("filename", "Unknown")
            doc_id = doc.get("document_id", "")
            pages = doc.get("total_pages", "?")
            timestamp = doc.get("upload_timestamp", "Unknown")
            # Format timestamp nicely
            if timestamp != "Unknown" and "T" in timestamp:
                timestamp = timestamp.split("T")[0]  # Just the date

            is_active = " (🟢 Active)" if doc_id == active_id else ""
            lines.append(f"{i}. 📄 `{filename}`{is_active}")
            lines.append(f"   Pages: {pages} | Uploaded: {timestamp}")

        lines.append("\n💡 *Tip:* Use /select to choose which document to query, or search all at once!")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error fetching documents for chat {chat_id} (user {user.id}): {e}")
        await update.message.reply_text(
            "❌ Could not fetch saved documents. Please try again."
        )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /status command.
    Shows bot status and chat's session info.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"/status in chat {chat_id} from user {user.id} ({user.first_name})")

    session = await session_manager.get_session(chat_id)
    active_users = await session_manager.get_active_user_count()

    try:
        doc_count = await vector_store.get_user_document_count(chat_id)
    except Exception:
        doc_count = "?"

    status_text = (
        "📊 **Bot Status**\n\n"
        f"👤 **Chat Session:**\n"
        f"• Chat ID: `{chat_id}`\n"
        f"• Chat messages: {len(session.chat_history)}\n"
        f"• Document chunks: {doc_count}\n"
        f"• Session started: {session.created_at.split('T')[0]}\n\n"
        f"🌐 **Bot Info:**\n"
        f"• Active sessions: {active_users}\n"
        f"• Status: ✅ Online\n"
    )

    await update.message.reply_text(status_text, parse_mode="Markdown")


async def select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /select command.
    Displays an inline keyboard to choose which document to query or search all.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"/select in chat {chat_id} from user {user.id} ({user.first_name})")

    try:
        docs_info = await vector_store.get_user_documents_info(chat_id)

        if not docs_info:
            await update.message.reply_text(
                "📭 No documents saved in this chat yet.\n\n"
                "Save a PDF file using the `/save` command!"
            )
            return

        session = await session_manager.get_session(chat_id)
        active_id = session.active_document_id

        # Build inline keyboard buttons
        keyboard = []
        for doc in docs_info:
            filename = doc.get("filename", "Unknown")
            doc_id = doc.get("document_id", "")
            
            # Highlight current active document
            display_name = f"🟢 {filename}" if doc_id == active_id else filename
            keyboard.append([InlineKeyboardButton(display_name, callback_data=f"select_doc:{doc_id}")])

        # Add Search All option
        all_name = "🟢 🔍 Search All Documents" if active_id is None else "🔍 Search All Documents"
        keyboard.append([InlineKeyboardButton(all_name, callback_data="select_all")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📂 **Choose Document to Query**\n\n"
            "Select which document you want your questions to answer from. "
            "Alternatively, choose 'Search All Documents' to look across all files in this chat.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error building select keyboard for chat {chat_id} (user {user.id}): {e}")
        await update.message.reply_text("❌ Failed to retrieve documents. Please try again.")


async def select_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle inline button clicks from /select.
    Updates the active document in the user session.
    """
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    
    await query.answer()

    try:
        session = await session_manager.get_session(chat_id)
        data = query.data

        if data == "select_all":
            session.active_document_id = None
            session.active_filename = None
            logger.info(f"User {user.id} ({user.first_name}) switched search mode to All Documents in chat {chat_id}")
            await query.edit_message_text(
                "✅ **Search Mode Updated**\n\n"
                "Now searching across **All Documents** saved in this chat.",
                parse_mode="Markdown",
            )
        elif data.startswith("select_doc:"):
            target_id = data.split(":", 1)[1]
            
            # Fetch user documents to find matching filename
            docs_info = await vector_store.get_user_documents_info(chat_id)
            target_doc = next((d for d in docs_info if d.get("document_id") == target_id), None)
            
            if target_doc:
                filename = target_doc.get("filename", "Unknown")
                session.active_document_id = target_id
                session.active_filename = filename
                logger.info(f"User {user.id} ({user.first_name}) selected active document '{filename}' in chat {chat_id}")
                await query.edit_message_text(
                    f"✅ **Search Mode Updated**\n\n"
                    f"Now querying only: `{filename}`",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text("❌ Document not found. Please try saving it again using `/save`.")

    except Exception as e:
        logger.error(f"Error handling select callback in chat {chat_id} (user {user.id}): {e}")
        await query.edit_message_text("❌ Failed to update active document. Please try /select again.")
