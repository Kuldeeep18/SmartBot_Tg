"""
Main Telegram Bot application.
Registers all handlers and starts the bot.
"""

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

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
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger
from telegram_bot.utils.decorators import enforce_group_tag


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

    # Build the application
    app = Application.builder().token(config.telegram_bot_token).build()

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
    
    # Also handle PDF uploads with /save in the caption
    app.add_handler(MessageHandler(
        filters.Document.PDF & filters.CaptionRegex(r"^/save(?:\s|@|$)"),
        enforce_group_tag(save_handler),
    ))
    
    app.add_handler(CallbackQueryHandler(select_callback_handler))

    # ──────────────────────────────────────
    # Register Text Handler (questions)
    # Must be registered LAST to avoid catching commands
    # ──────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        question_handler,
    ))

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
