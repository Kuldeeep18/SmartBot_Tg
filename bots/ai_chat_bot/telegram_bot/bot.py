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
    upload_handler,
    question_handler,
    reset_handler,
    mydocs_handler,
    status_handler,
    select_handler,
    select_callback_handler,
)
from telegram_bot.utils.config import config
from telegram_bot.utils.logger import logger


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
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("reset", reset_handler))
    app.add_handler(CommandHandler("mydocs", mydocs_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("select", select_handler))
    app.add_handler(CallbackQueryHandler(select_callback_handler))

    # ──────────────────────────────────────
    # Register Document Handler (PDF uploads)
    # ──────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.Document.PDF,
        upload_handler,
    ))

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
        allowed_updates=["message"],  # Only listen for messages
    )


if __name__ == "__main__":
    run()
