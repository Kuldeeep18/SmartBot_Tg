# Repomix Telegram Bot & PR Review Agent

A modular Node.js Telegram Bot that packages Git repositories using **Repomix** and reviews GitHub Pull Requests using **Google Gemini AI**.

This project is built as a highly reusable library. You can run the bot standalone or import the core packaging, GitHub diff, and LLM reviewer modules directly into your own applications.

---

## Features
- 🤖 **Interactive Telegram Bot**: Send any repository URL to pack it, or paste any GitHub Pull Request URL to trigger the review agent. Configure modes directly in chat via inline keyboard menus.
- 📦 **Multi-Style Repository Packaging**: Bundle your codebase into **XML**, **Markdown**, **Plain Text**, or **JSON** formats.
- 🔌 **Dynamic Branch Support**: Pack custom branches, tags, or commit hashes.
- 🔍 **Automated PR Reviews**: Parses GitHub PR links and runs one of four Gemini analysis modes:
  - **All-in-one Review 🏆**: High-level summaries, bug findings, security audits, and side-by-side refactoring suggestions.
  - **Code Review 🔍**: In-depth code quality audits, performance, and bug hunting.
  - **Changelog & Description 📖**: Automatic changelogs grouped by file/component.
  - **Improvements 💡**: Spots areas of refactoring and provides side-by-side Before/After code blocks.
- 🧹 **Automatic Cleanup**: Instantly deletes all temporary local files from the server after sending results to the user.

---

## Project Structure
```
github_bot_pr/
├── src/
│   ├── bot.js          # Interactive Telegram Bot controller using Telegraf
│   ├── packager.js     # Child process wrapper executing repomix
│   ├── analyzer.js     # Gemini API client for codebase audits
│   ├── github.js       # GitHub API client (metadata and raw diff fetcher)
│   └── prReviewer.js   # Gemini API client for PR code review reports
├── temp/               # Temporary folder for clones & output files (auto-managed)
├── index.js            # Entry point checking env and starting the bot
├── package.json        # Node.js dependencies
└── README.md           # Documentation
```

---

## Setup & Running

### 1. Installation
Ensure you have Git and **Node.js (>= 22.0.0)** installed. Clone or copy these files, and run:
```bash
npm install
```

### 2. Configuration
Create a `.env` file in the root directory (copy `.env.example` as a starting template) and add your configurations:
```env
# Get from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Get from Google AI Studio (https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# GitHub Token (Optional) - Needed to review PRs in PRIVATE repositories
GITHUB_TOKEN=your_github_pat_here

# Limit repository cloning size in MB
MAX_REPO_SIZE_MB=100
```

### 3. Run the Bot
To start the bot, run:
```bash
npm start
```

Once started, message your bot on Telegram and type `/start`. Paste either a Git Repository URL or a Pull Request URL to begin.

---

## Programmatic Integration (Reusing Core Logic)

You can import the core modules directly into your own project to fetch, bundle, or analyze code:

### 1. Repository Analyzer
```javascript
import { packRepository } from './src/packager.js';
import { analyzeRepository } from './src/analyzer.js';

// Pack and Audit a full repository
const stats = await packRepository('https://github.com/user/repo.git', { style: 'xml' });
const report = await analyzeRepository(stats.outputPath, 'repo-name');
console.log(report);
```

### 2. Pull Request Reviewer
```javascript
import { fetchPullRequestDetails, fetchPullRequestDiff } from './src/github.js';
import { analyzePullRequest } from './src/prReviewer.js';

// Fetch and Audit a Pull Request
const owner = 'yamadashy';
const repo = 'repomix';
const pullNumber = 150;

const details = await fetchPullRequestDetails(owner, repo, pullNumber);
const diff = await fetchPullRequestDiff(owner, repo, pullNumber);

// Run AI analysis (modes: 'all', 'review', 'describe', 'improve')
const reviewReport = await analyzePullRequest(details, diff, 'all');
console.log(reviewReport);
```
