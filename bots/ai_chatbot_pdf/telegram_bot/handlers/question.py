"""
Telegram bot handler: question answering.
Processes text messages through the RAG pipeline and returns answers with citations.
Correctly handles group mentions and replies, and operates on chat_id scope.
"""

import re
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import ContextTypes

from telegram_bot.models.user_session import session_manager
from telegram_bot.services.rag_chain import answer_query
from telegram_bot.utils.logger import logger
from telegram_bot.utils.text_splitter import split_message


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages as questions.
    """
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    if not update.message or not update.message.text:
        return

    query = update.message.text.strip()

    # Parse and strip command triggers (e.g. /ask, /chat, !ask, !chat, !bot) at the start of the message
    trigger_match = re.match(r"^(?:/ask|/chat|!ask|!chat|!bot)(?:@\w+)?\s*", query, re.IGNORECASE)
    is_command_trigger = False
    if trigger_match:
        query = query[trigger_match.end():].strip()
        is_command_trigger = True

    # Group Chat Mentions and Replies Logic
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        bot_username = context.bot.username or ""
        if not bot_username:
            try:
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username or ""
            except Exception as e:
                logger.warning(f"Could not fetch bot username dynamically: {e}")
        
        bot_tag = f"@{bot_username}" if bot_username else ""
        is_tagged = is_command_trigger

        if bot_tag:
            # 1. Check if bot is explicitly tagged/mentioned via message entities
            if update.message.entities:
                for entity in update.message.entities:
                    if entity.type == "mention":
                        mention_text = query[entity.offset : entity.offset + entity.length]
                        if mention_text.lower() == bot_tag.lower():
                            is_tagged = True
                            break
            
            # 2. Fallback check: check if the tag is anywhere in the query string
            if not is_tagged:
                is_tagged = bot_tag.lower() in query.lower()

        # 3. Check if the message is replying to one of the bot's messages
        is_reply_to_bot = (
            update.message.reply_to_message and
            update.message.reply_to_message.from_user.id == context.bot.id
        )

        # Ignore if not tagged and not replying to the bot
        if not (is_tagged or is_reply_to_bot):
            return

        user_name = user.first_name or "Unknown"
        logger.info(f"Group question in chat {chat_id} from user {user.id} ({user_name}): '{query[:80]}...'")

        # Clean out bot tag mentions so they don't corrupt document query matching
        if bot_username:
            query = re.sub(rf"(?i)@{re.escape(bot_username)}", "", query).strip()
    else:
        user_name = user.first_name or "Unknown"
        logger.info(f"Private question in chat {chat_id} from user {user.id} ({user_name}): '{query[:80]}...'")

    if not query:
        # Prompt user if they only tagged the bot
        await update.message.reply_text("👋 Hello! How can I help you with your saved documents today?")
        return

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Get chat session scope
        session = await session_manager.get_session(chat_id)

        # Run the RAG pipeline
        result = await answer_query(
            query=query,
            telegram_user_id=chat_id,
            chat_history=session.chat_history,
            document_id=session.active_document_id,
        )

        answer = result["answer"]
        route = result["route"]

        logger.info(
            f"Answer generated for chat {chat_id}: route={route}, "
            f"sources={len(result['sources'])}, answer_len={len(answer)}"
        )

        # Split long messages for Telegram's 4096 char limit
        message_parts = split_message(answer)

        for part in message_parts:
            try:
                await update.message.reply_text(
                    part,
                    parse_mode="Markdown",
                )
            except Exception:
                # Fallback: send without Markdown if parsing fails
                await update.message.reply_text(part)

        # Update chat history
        session.add_message("user", query)
        session.add_message("assistant", answer)
        await session_manager.save_session(chat_id)

    except Exception as e:
        logger.error(f"Error answering question in chat {chat_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, I encountered an error while processing your question.\n"
            "Please try again. If the problem persists, use /reset to start a fresh session."
        )
