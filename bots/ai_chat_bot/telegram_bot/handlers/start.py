"""
Telegram bot handlers: /start and /help commands.
"""

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.utils.logger import logger

WELCOME_MESSAGE = """
🤖 **Welcome to the PDF Chatbot!**

I'm your AI-powered PDF assistant. I can help you understand and answer questions from your PDF documents.

**Here's how to use me:**

📄 **Save a PDF** — Upload a PDF with `/save` as the caption, or reply `/save` to any PDF in the chat
❓ **Ask a question** — Type your query. (In group chats, you must tag/mention me)
📚 **Get cited answers** — I'll reference specific pages and sources

**Commands:**
/start — Show this welcome message
/help — Detailed help & tips
/save — Ingest a PDF (by reply or caption)
/mydocs — List saved documents in this chat
/select — Choose active document to query
/reset — Clear chat history (preserves docs)
/status — Check bot status

**Get started** by sending a PDF with `/save` as its caption! 📎
"""

HELP_MESSAGE = """
📖 **Detailed Help**

**Saving Documents:**
• Upload a PDF file and set the caption to `/save`
• Or reply `/save` to any PDF file already sent in the chat
• Only files explicitly saved via `/save` are added to the search index
• In group chats, documents are scoped to the group so all members can search them

**Asking Questions:**
• In private chats, just type your question normally
• In group chats, you must mention me (e.g. `@your_bot_name ...`) or reply directly to one of my messages
• I'll search through your chat's saved documents and cite specific page numbers

**Tips:**
• 💡 Save the PDF with `/save` first, then ask questions
• 💡 Be specific — "What is the ROI on page 5?" works better than "Tell me about it"
• 💡 Use `/select` to choose which document to query (so you don't get mixed results from other PDFs)
• 💡 I can answer general questions too (no PDF needed)
• 💡 Use `/reset` to start a fresh conversation

**Supported LLM Providers:**
OpenAI, Gemini, Groq, OpenRouter — configurable by the bot admin.

**Having issues?** Make sure your PDF contains selectable text (not scanned images).
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    logger.info(f"/start from user {user.id} ({user.first_name})")

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    user = update.effective_user
    logger.info(f"/help from user {user.id} ({user.first_name})")

    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode="Markdown",
    )
