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

📄 **Upload a PDF** — Just send me a PDF file and I'll process it
❓ **Ask a question** — Type any question about your uploaded documents
📚 **Get cited answers** — I'll reference specific pages and sources

**Commands:**
/start — Show this welcome message
/help — Detailed help & tips
/mydocs — List your uploaded documents
/select — Choose which document to query or search all
/reset — Clear your chat history
/status — Check bot status

**Get started** by uploading a PDF document! 📎
"""

HELP_MESSAGE = """
📖 **Detailed Help**

**Uploading Documents:**
• Send me any PDF file (up to 20MB)
• I'll extract the text, chunk it, and store it for searching
• You can upload multiple PDFs — each one is added to your knowledge base
• Your documents are private — other users cannot see them

**Asking Questions:**
• After uploading a PDF, just type your question as a normal message
• I'll search through your documents for the most relevant information
• I'll cite specific page numbers and filenames in my answers
• For best results, ask specific questions

**Tips:**
• 💡 Upload the PDF first, then ask questions
• 💡 Be specific — "What is the ROI on page 5?" works better than "Tell me about it"
• 💡 Use /select to choose which document to query (so you don't get mixed results from other PDFs)
• 💡 I can answer general questions too (no PDF needed)
• 💡 Use /reset to start a fresh conversation

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
