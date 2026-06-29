"""
Decorators for Telegram bot handlers.
"""

from functools import wraps
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from telegram_bot.utils.logger import logger


def enforce_group_tag(handler_func):
    """
    Decorator that enforces bot tagging for command updates in group chats.
    If the update is in a group/supergroup and the bot username is not tagged
    in the message text or caption, the update is ignored.
    """
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Only enforce in group/supergroup chats
        if update.effective_chat and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            # Fetch bot username dynamically
            bot_username = context.bot.username or ""
            if not bot_username:
                try:
                    bot_info = await context.bot.get_me()
                    bot_username = bot_info.username or ""
                except Exception as e:
                    logger.warning(f"Could not fetch bot username in decorator: {e}")

            if bot_username:
                bot_tag = f"@{bot_username}".lower()
                message = update.message or update.edited_message
                msg_text = ""
                if message:
                    msg_text = message.text or message.caption or ""

                # If the bot tag is not in the message text, ignore the command
                if bot_tag not in msg_text.lower():
                    logger.debug(f"Ignoring command in chat {update.effective_chat.id}: bot tag '{bot_tag}' not found in message.")
                    return

        return await handler_func(update, context, *args, **kwargs)

    return wrapper
