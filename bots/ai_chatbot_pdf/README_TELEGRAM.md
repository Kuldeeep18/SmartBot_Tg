# Telegram RAG PDF Chatbot

A Telegram bot that lets users upload PDF documents and ask questions about them, powered by the existing LangChain RAG pipeline.

## 🏗️ Architecture

```
User → Telegram Bot → PDF Processor → Vector Store (Supabase)
                    → RAG Chain → LLM (OpenAI/Gemini/Groq) → Answer with Citations
```

The bot reuses the same **Supabase vector store** and **embedding model** as the existing TypeScript frontend, so documents are compatible across both interfaces.

## 📁 Project Structure

```
Ai-rag-tel/
├── telegram_bot/
│   ├── bot.py                  # Main entry point
│   ├── handlers/
│   │   ├── start.py            # /start, /help commands
│   │   ├── upload.py           # PDF upload processing
│   │   ├── question.py         # Question answering via RAG
│   │   └── session.py          # /reset, /mydocs, /status
│   ├── services/
│   │   ├── embeddings.py       # OpenAI embedding singleton
│   │   ├── vector_store.py     # Supabase vector store ops
│   │   ├── pdf_processor.py    # PDF parsing + chunking
│   │   └── rag_chain.py        # RAG pipeline (route → retrieve → generate)
│   ├── models/
│   │   └── user_session.py     # In-memory session management
│   └── utils/
│       ├── config.py           # Environment config loader
│       ├── logger.py           # Logging setup
│       └── text_splitter.py    # Telegram message splitting
├── storage/
│   └── uploaded_pdfs/          # Local PDF storage (per user)
├── .env                        # Your configuration (not committed)
├── .env.example                # Template
├── requirements.txt            # Python dependencies
├── run_bot.py                  # Quick start script
└── README_TELEGRAM.md          # This file
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Telegram Bot Token** — Get one from [@BotFather](https://t.me/BotFather)
- **Supabase Project** — With the `documents` table and `match_documents` function configured
- **LLM API Key** — OpenAI, Gemini, Groq, or OpenRouter

### Step 1: Install Dependencies

```bash
cd Ai-rag-tel
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=your-openai-key

# Optional: Switch LLM provider
LLM_PROVIDER=openai          # openai | gemini | groq | openrouter
LLM_MODEL=gpt-4o-mini
```

### Step 3: Create Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token into your `.env` file

### Step 4: Run the Bot

```bash
python run_bot.py
```

You should see:
```
🤖 Telegram PDF Chatbot is starting...
   LLM Provider: openai
   LLM Model: gpt-4o-mini
   ...
```

### Step 5: Test It!

1. Open your bot in Telegram
2. Send `/start`
3. Upload a PDF document
4. Ask questions about the document!

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and usage guide |
| `/help` | Detailed help and tips |
| `/mydocs` | List your uploaded documents |
| `/reset` | Clear chat history |
| `/status` | Bot status and session info |

## ⚙️ Configuration

### LLM Providers

| Provider | `LLM_PROVIDER` | `LLM_MODEL` (example) | API Key Env Var |
|----------|----------------|------------------------|-----------------|
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Gemini | `gemini` | `gemini-1.5-flash` | `GOOGLE_API_KEY` |
| Groq | `groq` | `llama-3.1-70b-versatile` | `GROQ_API_KEY` |
| OpenRouter | `openrouter` | `openai/gpt-4o-mini` | `OPENROUTER_API_KEY` |

### RAG Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | 1000 | Characters per text chunk |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `RETRIEVER_K` | 5 | Number of documents to retrieve |

## 🔒 Multi-User Isolation

Each user's documents are tagged with their `telegram_user_id` in the vector store metadata. When a user asks a question, only their own documents are searched. This ensures complete privacy between users.

## 📖 How It Works

1. **PDF Upload**: User sends a PDF → saved locally → parsed with PyPDFLoader → chunked with RecursiveCharacterTextSplitter → embedded with OpenAI → stored in Supabase
2. **Question**: User sends text → query routing (retrieve vs direct) → similarity search on user's documents → LLM generates answer with citations
3. **Citations**: Each answer includes page numbers and source filenames from the retrieved chunks

## 🚢 Deployment

### Railway / Render

1. Push your code to a Git repository
2. Set all `.env` variables as environment variables in your platform
3. Set the start command to: `python run_bot.py`
4. Deploy!

The bot uses **polling mode** by default, which works on any platform without webhook configuration.

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Check `TELEGRAM_BOT_TOKEN` is correct |
| "API key not set" error | Ensure the API key for your `LLM_PROVIDER` is set |
| Empty search results | Make sure you've uploaded a PDF first |
| PDF processing fails | Ensure the PDF contains selectable text (not scanned images) |
| Supabase errors | Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are correct |
