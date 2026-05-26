"""
Telegram bot handler: question answering.
Processes text messages through the RAG pipeline and returns answers with citations.
"""

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bot.models.user_session import session_manager
from telegram_bot.services.rag_chain import answer_query
from telegram_bot.utils.logger import logger
from telegram_bot.utils.text_splitter import split_message


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle text messages as questions.

    Flow:
    1. Show "typing..." indicator
    2. Get user session and chat history
    3. Run the RAG pipeline (route → retrieve → generate)
    4. Send the response (split if too long)
    5. Update chat history
    """
    user = update.effective_user
    query = update.message.text.strip()

    if not query:
        return

    logger.info(f"Question from user {user.id} ({user.first_name}): '{query[:80]}...'")

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        # Get user session
        session = await session_manager.get_session(user.id)

        # Run the RAG pipeline
        result = await answer_query(
            query=query,
            telegram_user_id=user.id,
            chat_history=session.chat_history,
            document_id=session.active_document_id,
        )

        answer = result["answer"]
        route = result["route"]

        logger.info(
            f"Answer generated for user {user.id}: route={route}, "
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

    except Exception as e:
        logger.error(f"Error answering question for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, I encountered an error while processing your question.\n"
            "Please try again. If the problem persists, use /reset to start a fresh session."
        )
