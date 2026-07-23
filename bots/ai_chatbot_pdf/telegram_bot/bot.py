import re
import traceback

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

from telegram_bot.handlers import (
    start_handler,
    help_handler,
    save_handler,
    question_handler,
    reset_handler,
    mydocs_handler,
    status_handler,
    select_handler,
    select_callback_handler,
)
from telegram_bot.handlers.permsave import (
    permsave_handler,
    permsave_callback_handler,
    initialize_startup_cleanup,
)
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger
from telegram_bot.utils.decorators import enforce_group_tag

# ──────────────────────────────────────
# Map of command names to their handler functions
# Used by group_command_dispatcher to route "@botname /command" messages
# ──────────────────────────────────────
COMMAND_MAP = {
    "start": start_handler,
    "help": help_handler,
    "reset": reset_handler,
    "mydocs": mydocs_handler,
    "status": status_handler,
    "select": select_handler,
    "save": save_handler,
    "ask": question_handler,
    "chat": question_handler,
    "permanentsave": permsave_handler,
}

# Regex: @botname /command  (with optional text after)
# Captures: group(1) = bot_username, group(2) = command_name
_TAG_THEN_COMMAND_RE = re.compile(
    r"^@(\S+)\s+/(\w+)(?:\s|$)", re.IGNORECASE
)


async def group_command_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatch '@botname /command ...' messages in group chats.

    Telegram only recognises '/command' and '/command@botname' as commands.
    Users in groups naturally type '@botname /command', which Telegram treats
    as regular text.  This handler intercepts that pattern, validates the bot
    tag, and forwards to the correct handler.
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    match = _TAG_THEN_COMMAND_RE.match(text)
    if not match:
        return

    mentioned_username = match.group(1).lower()
    command_name = match.group(2).lower()

    # Make sure the mention is actually for THIS bot
    bot_username = (context.bot.username or "").lower()
    if not bot_username:
        try:
            bot_info = await context.bot.get_me()
            bot_username = (bot_info.username or "").lower()
        except Exception:
            return

    if mentioned_username != bot_username:
        return  # Tagged a different bot, ignore

    handler_func = COMMAND_MAP.get(command_name)
    if handler_func:
        logger.info(
            f"Dispatching '@{bot_username} /{command_name}' in chat "
            f"{update.effective_chat.id} from user {update.effective_user.id}"
        )
        await handler_func(update, context)
    else:
        # Unknown command — let the question handler deal with it
        await question_handler(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the Telegram bot.

    Logs transient network errors (DNS failures, timeouts) at WARNING level
    and all other unexpected errors at ERROR level with full tracebacks.
    The polling loop will automatically retry after network errors.
    """
    error = context.error

    # Transient network issues – log briefly, polling will retry
    if isinstance(error, (NetworkError, TimedOut, ConnectionError, OSError)):
        logger.warning(
            "Transient network error (will retry automatically): %s: %s",
            type(error).__name__,
            error,
        )
        return

    # Unexpected errors – log full traceback for debugging
    tb_string = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logger.error(
        "Unhandled exception while processing an update:\n%s",
        tb_string,
    )

    # Optionally notify the user that something went wrong
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again."
            )
        except Exception:
            logger.warning("Failed to send error message to user.")


def create_bot() -> Application:
    """
    Create and configure the Telegram bot application.

    Returns:
        Configured Application instance.
    """
    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        raise RuntimeError(
            "Configuration errors found:\n" + "\n".join(f"  • {e}" for e in errors)
        )

    # Ensure required directories exist
    config.ensure_dirs()

    logger.info("Building Telegram bot application...")

    # Build the application with custom timeouts and post_init startup cleanup hook
    request_config = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    app = (
        Application.builder()
        .token(config.telegram_bot_token)
        .request(request_config)
        .post_init(initialize_startup_cleanup)
        .build()
    )

    # ──────────────────────────────────────
    # Register Command Handlers
    # ──────────────────────────────────────
    app.add_handler(CommandHandler("start", enforce_group_tag(start_handler)))
    app.add_handler(CommandHandler("help", enforce_group_tag(help_handler)))
    app.add_handler(CommandHandler("reset", enforce_group_tag(reset_handler)))
    app.add_handler(CommandHandler("mydocs", enforce_group_tag(mydocs_handler)))
    app.add_handler(CommandHandler("status", enforce_group_tag(status_handler)))
    app.add_handler(CommandHandler("select", enforce_group_tag(select_handler)))
    app.add_handler(CommandHandler("save", enforce_group_tag(save_handler)))
    app.add_handler(CommandHandler("ask", enforce_group_tag(question_handler)))
    app.add_handler(CommandHandler("chat", enforce_group_tag(question_handler)))
    app.add_handler(CommandHandler("permanentSave", enforce_group_tag(permsave_handler)))
    app.add_handler(CommandHandler("permanentsave", enforce_group_tag(permsave_handler)))
    
    # Also handle uploads with /save in the caption
    # Matches: "/save", "@botname /save", "/save@botname"
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.CaptionRegex(r"(?:^|\s)/save(?:\s|@|$)|^@\S+\s+/save(?:\s|$)"),
        enforce_group_tag(save_handler),
    ))
    
    app.add_handler(CallbackQueryHandler(permsave_callback_handler, pattern="^permsave_"))
    app.add_handler(CallbackQueryHandler(select_callback_handler))

    # ──────────────────────────────────────
    # Dispatch "@botname /command" in group chats
    # Telegram treats this as plain text, not a command.
    # Must be registered BEFORE the catch-all text handler.
    # ──────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.Regex(_TAG_THEN_COMMAND_RE) & ~filters.COMMAND,
        group_command_dispatcher,
    ))

    # ──────────────────────────────────────
    # Register Text Handler (questions)
    # Must be registered LAST to avoid catching commands
    # ──────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        question_handler,
    ))

    # ──────────────────────────────────────
    # Register Global Error Handler
    # ──────────────────────────────────────
    app.add_error_handler(error_handler)

    logger.info("All handlers registered successfully")
    return app


def run():
    """Start the bot with polling (for local development)."""
    app = create_bot()

    logger.info("=" * 50)
    logger.info("Telegram PDF Chatbot is starting...")
    logger.info(f"   LLM Provider: {config.llm_provider}")
    logger.info(f"   LLM Model: {config.llm_model}")
    logger.info(f"   Embedding: {config.embedding_model}")
    logger.info(f"   Retriever K: {config.retriever_k}")
    logger.info(f"   Chunk Size: {config.chunk_size}")
    logger.info(f"   Upload Dir: {config.upload_dir}")
    logger.info("=" * 50)

    # Start polling
    app.run_polling(
        drop_pending_updates=True,  # Ignore messages sent while bot was offline
        allowed_updates=["message", "callback_query"],  # Listen for both messages and inline button clicks
    )


if __name__ == "__main__":
    run()
