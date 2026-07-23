import { Telegraf, Markup } from 'telegraf';
import path from 'path';
import fs from 'fs-extra';
import { fileURLToPath } from 'url';
import { packRepository, validateRepoUrl, validateBranch } from './packager.js';
import { analyzeRepository } from './analyzer.js';
import { parsePullRequestUrl, fetchPullRequestDetails, fetchPullRequestDiff, checkCollaboratorPermission, mergePullRequest, closePullRequest } from './github.js';
import { analyzePullRequest } from './prReviewer.js';
import { getOAuthUrl, getUserCredentials, disconnectUser } from './oauth.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// In-memory state storage for user session settings
// Key: chatId, Value: { type, url, style, analyze, branch, waitingForBranch, owner, repo, pullNumber, mode }
const userSessions = new Map();

/**
 * Initialize and start the Telegram Bot
 * @param {string} token - Telegram Bot Token
 */
export function startBot(token) {
  if (!token) {
    console.warn('\n⚠️  WARNING: TELEGRAM_BOT_TOKEN is not set in your .env file.');
    console.warn('The Telegram bot will not start. Please add your token to the .env file once created.\n');
    return null;
  }

  const bot = new Telegraf(token);

  const ALL_PR_PLUGINS = ['pr_review', 'pr_description', 'code_improvements', 'security_audit'];

  const getEnabledPlugins = () => {
    const envVar = process.env.ENABLED_PLUGINS;
    if (!envVar || !envVar.trim()) {
      return new Set(ALL_PR_PLUGINS);
    }
    return new Set(envVar.split(',').map(p => p.trim()).filter(Boolean));
  };

  const isPluginEnabled = (pluginKey) => {
    return getEnabledPlugins().has(pluginKey);
  };

  // Helper to handle PR slash commands
  const handlePRSlashCommand = async (ctx, pluginKey, mode, commandName, friendlyName) => {
    if (!isPluginEnabled(pluginKey)) {
      return ctx.replyWithHTML(`⚠️ The <code>/${commandName}</code> template feature (<b>${friendlyName}</b>) is not enabled for this bot container.`);
    }

    const text = ctx.message.text.trim();
    const parts = text.split(/\s+/);
    const prUrlArg = parts.find(p => p.toLowerCase().includes('github.com') && p.toLowerCase().includes('/pull/'));

    if (prUrlArg) {
      try {
        const { owner, repo, pullNumber } = parsePullRequestUrl(prUrlArg);
        const state = {
          type: 'pr',
          url: prUrlArg,
          owner,
          repo,
          pullNumber,
          mode
        };
        userSessions.set(ctx.chat.id, state);
        await ctx.replyWithHTML(getStatusText(state), getMenuMarkup(state));
        return;
      } catch (err) {
        return ctx.reply(`❌ Invalid PR URL provided: ${err.message}`);
      }
    }

    ctx.replyWithHTML(
      `🔍 <b>${friendlyName} Command</b> (<code>/${commandName}</code>)\n\n` +
      `Please provide a GitHub PR URL to run this analysis.\n\n` +
      `<b>Usage:</b>\n` +
      `<code>/${commandName} https://github.com/owner/repository/pull/123</code>`
    );
  };

  // Slash Command: /review -> Automated PR Review
  bot.command('review', (ctx) => {
    handlePRSlashCommand(ctx, 'pr_review', 'review', 'review', 'Automated PR Review');
  });

  // Slash Command: /describe -> PR Description & Changelog
  bot.command('describe', (ctx) => {
    handlePRSlashCommand(ctx, 'pr_description', 'describe', 'describe', 'PR Description & Changelog');
  });

  // Slash Command: /improve -> Refactoring & Code Suggestions
  bot.command('improve', (ctx) => {
    handlePRSlashCommand(ctx, 'code_improvements', 'improve', 'improve', 'Refactoring & Code Suggestions');
  });

  // Slash Command: /security or /audit -> Security & Secret Scanner
  bot.command('security', (ctx) => {
    handlePRSlashCommand(ctx, 'security_audit', 'security_audit', 'security', 'Security & Secret Scanner');
  });
  bot.command('audit', (ctx) => {
    handlePRSlashCommand(ctx, 'security_audit', 'security_audit', 'security', 'Security & Secret Scanner');
  });

  // Command: /start
  bot.start((ctx) => {
    const username = ctx.from.first_name || 'Developer';
    ctx.replyWithHTML(
      `🤖 <b>Welcome to the Repomix Repo & PR Review Bot, ${username}!</b>\n\n` +
      `I can help you package codebases and manage/review PR changes.\n\n` +
      `📦 <b>Repo Analyzer:</b> Send any Git repository URL to pack & analyze.\n\n` +
      `🔍 <b>Active Template Commands:</b>\n` +
      `/review [pr_url] - Automated PR Review\n` +
      `/describe [pr_url] - PR Description & Changelog\n` +
      `/improve [pr_url] - Code Refactoring & Suggestions\n` +
      `/security [pr_url] - Security & Secret Audit\n\n` +
      `🔐 <b>GitHub Account:</b> Use /login and /logout to link your GitHub account.`
    );
  });

  // Command: /login
  bot.command('login', (ctx) => {
    const chatId = ctx.chat.id;
    try {
      const creds = getUserCredentials(chatId);
      if (creds) {
        return ctx.replyWithHTML(`✅ You are already authenticated as GitHub user: <b>@${creds.username}</b>.`);
      }
      const url = getOAuthUrl(chatId);
      ctx.replyWithHTML(
        `🔑 <b>Link your GitHub Account</b>\n\n` +
        `Click the link below to authorize the bot to manage PRs (merge, close) in repositories you contribute to:\n\n` +
        `<a href="${url}">👉 Connect GitHub Account</a>`,
        { disable_web_page_preview: true }
      );
    } catch (err) {
      ctx.reply(`❌ OAuth configuration error: ${err.message}\nEnsure GITHUB_CLIENT_ID and OAUTH_REDIRECT_URL are set in the .env file.`);
    }
  });

  // Command: /logout
  bot.command('logout', async (ctx) => {
    const chatId = ctx.chat.id;
    const creds = getUserCredentials(chatId);
    if (!creds) {
      return ctx.reply('You are not connected to any GitHub account.');
    }
    await disconnectUser(chatId);
    ctx.replyWithHTML(`🔌 Disconnected from GitHub account: <b>@${creds.username}</b>.`);
  });

  // Help description
  bot.help((ctx) => {
    const enabled = getEnabledPlugins();
    let helpText = '🤖 <b>GitHub PR Reviewer Commands:</b>\n\n';

    if (enabled.has('pr_review')) {
      helpText += '🔍 <b>/review [pr_url]</b> - Automated AI review for bugs, syntax & style\n';
    }
    if (enabled.has('pr_description')) {
      helpText += '📝 <b>/describe [pr_url]</b> - Auto-generate PR overview, changelog & checklist\n';
    }
    if (enabled.has('code_improvements')) {
      helpText += '💡 <b>/improve [pr_url]</b> - Line-by-line code refactoring & suggestions\n';
    }
    if (enabled.has('security_audit')) {
      helpText += '🔒 <b>/security [pr_url]</b> - Security audit for vulnerabilities & secret leaks\n';
    }

    helpText += '\n🔐 <b>GitHub Account:</b>\n' +
      '/login - Connect your GitHub account\n' +
      '/logout - Disconnect your GitHub account\n\n' +
      '💡 You can also send a raw GitHub PR URL or Repository URL in chat!';

    ctx.replyWithHTML(helpText);
  });

  const getAvailableModes = () => {
    const enabled = getEnabledPlugins();
    const modes = [];
    if (enabled.has('pr_review')) modes.push('review');
    if (enabled.has('pr_description')) modes.push('describe');
    if (enabled.has('code_improvements')) modes.push('improve');
    if (enabled.has('security_audit')) modes.push('security_audit');
    if (modes.length === 0) modes.push('review');
    return modes;
  };

  // Action: Configuration Menu builder
  const getMenuMarkup = (state) => {
    if (state.type === 'pr') {
      const modeLabel = {
        review: 'Code Review 🔍',
        describe: 'Changelog & Description 📖',
        improve: 'Improvements & Refactoring 💡',
        security_audit: 'Security Audit 🔒',
        all: 'All-in-one Review 🏆'
      }[state.mode] || 'Code Review 🔍';

      return Markup.inlineKeyboard([
        [Markup.button.callback(`Review Mode: ${modeLabel}`, 'toggle_pr_mode')],
        [
          Markup.button.callback('🟢 Merge PR', 'execute_pr_merge'),
          Markup.button.callback('🔴 Close PR', 'execute_pr_close')
        ],
        [
          Markup.button.callback('❌ Cancel', 'cancel_pack'),
          Markup.button.callback('🚀 Start Review', 'execute_pr_review')
        ]
      ]);
    }

    const styleLabel = {
      xml: 'XML (Default) 📂',
      markdown: 'Markdown 📝',
      plain: 'Plain Text 📄'
    }[state.style];

    const aiLabel = state.analyze ? 'Gemini AI Analysis: ON 🤖' : 'Gemini AI Analysis: OFF ❌';
    const branchLabel = state.branch ? `Branch: ${state.branch} 🔌` : 'Branch: Default branch 🔗';

    return Markup.inlineKeyboard([
      [Markup.button.callback(`Style: ${styleLabel}`, 'toggle_style')],
      [Markup.button.callback(aiLabel, 'toggle_ai')],
      [Markup.button.callback(branchLabel, 'change_branch')],
      [
        Markup.button.callback('❌ Cancel', 'cancel_pack'),
        Markup.button.callback('🚀 Start Packing', 'execute_pack')
      ]
    ]);
  };

  // Helper to escape HTML characters
  const escapeHtml = (unsafe) => {
    if (!unsafe) return '';
    return unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  // Helper to print config settings status
  const getStatusText = (state) => {
    if (state.type === 'pr') {
      return `🔍 <b>GitHub Pull Request Detected!</b>\n\n` +
        `• <b>Repository:</b> <code>${escapeHtml(state.owner)}/${escapeHtml(state.repo)}</code>\n` +
        `• <b>PR Number:</b> <code>#${state.pullNumber}</code>\n\n` +
        `Configure your review preferences below:`;
    }

    const escapedUrl = escapeHtml(state.url);
    const branchLine = state.branch ? `\n🔌 <b>Branch:</b> <code>${escapeHtml(state.branch)}</code>` : '';
    return `📦 <b>Target Repository:</b> <code>${escapedUrl}</code>${branchLine}\n\n` +
      `Configure your preferences below:`;
  };

  // Text message handler (detecting git repo urls, PR links, or branch inputs)
  bot.on('text', async (ctx) => {
    const chatId = ctx.chat.id;
    const text = ctx.message.text.trim();
    
    // Ignore slash commands so bot.command handlers process them exclusively
    if (text.startsWith('/')) return;

    const state = userSessions.get(chatId);

    // Case 1: Conversational branch input (Repo Analyzer mode only)
    if (state && state.waitingForBranch) {
      try {
        if (text.toLowerCase() === 'default' || text === '-') {
          state.branch = null;
        } else {
          state.branch = validateBranch(text);
        }
        state.waitingForBranch = false;
        userSessions.set(chatId, state);

        await ctx.reply(`Branch set successfully! Returning to menu...`);
        await ctx.replyWithHTML(getStatusText(state), getMenuMarkup(state));
      } catch (err) {
        ctx.reply(`❌ ${err.message}\nSend a valid branch name or type 'default' to clear:`);
      }
      return;
    }

    // Case 2: Treat input as GitHub Pull Request URL
    if (text.toLowerCase().includes('github.com') && text.toLowerCase().includes('/pull/')) {
      try {
        const { owner, repo, pullNumber } = parsePullRequestUrl(text);
        
        const newState = {
          type: 'pr',
          url: text,
          owner,
          repo,
          pullNumber,
          mode: 'all'
        };
        
        userSessions.set(chatId, newState);
        await ctx.replyWithHTML(getStatusText(newState), getMenuMarkup(newState));
        return;
      } catch (err) {
        console.warn(`Dynamic PR routing failed: ${err.message}. Cascading to Repo routing...`);
      }
    }

    // Case 3: Treat input as Git Repository URL
    try {
      const validatedUrl = validateRepoUrl(text);
      
      // Initialize state for user
      const newState = {
        url: validatedUrl,
        style: 'xml',
        analyze: true,
        branch: null,
        waitingForBranch: false
      };
      
      userSessions.set(chatId, newState);

      await ctx.replyWithHTML(getStatusText(newState), getMenuMarkup(newState));
    } catch (err) {
      console.warn(`Input validation failed: "${text}". Error: ${err.message}`);
      ctx.reply(`❌ Not a valid repository or Pull Request URL.\n` +
        `• For Repos, send: <code>https://github.com/user/repo</code>\n` +
        `• For PRs, send: <code>https://github.com/user/repo/pull/123</code>`);
    }
  });

  // Action Handler: Cycle PR Review Mode among enabled templates
  bot.action('toggle_pr_mode', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state || state.type !== 'pr') return ctx.answerCbQuery('Session expired.');

    const availableModes = getAvailableModes();
    let currIdx = availableModes.indexOf(state.mode);
    if (currIdx === -1) currIdx = 0;

    const nextMode = availableModes[(currIdx + 1) % availableModes.length];
    state.mode = nextMode;
    userSessions.set(chatId, state);

    try {
      await ctx.editMessageText(
        getStatusText(state),
        {
          parse_mode: 'HTML',
          reply_markup: getMenuMarkup(state).reply_markup
        }
      );
    } catch (e) {
      // Ignore message unchanged errors
    }
    ctx.answerCbQuery();
  });

  // Action Handler: Toggle Style
  bot.action('toggle_style', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state) return ctx.answerCbQuery('Session expired.');

    const nextStyle = {
      xml: 'markdown',
      markdown: 'plain',
      plain: 'xml'
    }[state.style];

    state.style = nextStyle;
    userSessions.set(chatId, state);

    try {
      await ctx.editMessageText(
        getStatusText(state),
        {
          parse_mode: 'HTML',
          reply_markup: getMenuMarkup(state).reply_markup
        }
      );
    } catch (e) {
      // Ignore message unchanged errors
    }
    ctx.answerCbQuery();
  });

  // Action Handler: Toggle AI Audit
  bot.action('toggle_ai', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state) return ctx.answerCbQuery('Session expired.');

    state.analyze = !state.analyze;
    userSessions.set(chatId, state);

    try {
      await ctx.editMessageText(
        getStatusText(state),
        {
          parse_mode: 'HTML',
          reply_markup: getMenuMarkup(state).reply_markup
        }
      );
    } catch (e) {
      // Ignore
    }
    ctx.answerCbQuery();
  });

  // Action Handler: Change Branch
  bot.action('change_branch', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state) return ctx.answerCbQuery('Session expired.');

    state.waitingForBranch = true;
    userSessions.set(chatId, state);

    await ctx.reply(
      '🔌 Please send the branch name, tag, or commit hash (e.g., "main", "dev", "v1.2.0").\n' +
      'Type "default" to use the repository\'s default branch.'
    );
    ctx.answerCbQuery();
  });

  // Action Handler: Cancel
  bot.action('cancel_pack', async (ctx) => {
    const chatId = ctx.chat?.id;
    userSessions.delete(chatId);
    await ctx.editMessageText('❌ Request cancelled.');
    ctx.answerCbQuery();
  });

  // Action Handler: Merge PR
  bot.action('execute_pr_merge', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state || state.type !== 'pr') return ctx.answerCbQuery('Session expired.');

    // 1. Check Authentication
    const creds = getUserCredentials(chatId);
    if (!creds) {
      try {
        const url = getOAuthUrl(chatId);
        return ctx.replyWithHTML(
          `🔑 <b>Authentication Required</b>\n\n` +
          `To merge pull requests, you must connect your GitHub account:\n\n` +
          `<a href="${url}">👉 Connect GitHub Account</a>\n\n` +
          `Once connected, click the <b>🟢 Merge PR</b> button again.`,
          { disable_web_page_preview: true }
        );
      } catch (err) {
        return ctx.reply(`❌ OAuth configuration missing: ${err.message}`);
      }
    }

    ctx.answerCbQuery('Checking merge permissions...');
    userSessions.delete(chatId); // Clear session

    let statusMsg;
    try {
      statusMsg = await ctx.reply('⏳ Verifying collaborator push permission on GitHub...', { parse_mode: 'HTML' });

      // 2. Verify Collaborator push permission
      const hasWriteAccess = await checkCollaboratorPermission(state.owner, state.repo, creds.username, creds.token);
      
      if (!hasWriteAccess) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
        return ctx.replyWithHTML(
          `❌ <b>Permission Denied</b>\n\n` +
          `GitHub user <b>@${creds.username}</b> does not have push (write/admin) access to the repository ` +
          `<code>${state.owner}/${state.repo}</code>.\n` +
          `Only repository contributors with push permissions can merge pull requests.`
        );
      }

      await ctx.telegram.editMessageText(
        chatId,
        statusMsg.message_id,
        null,
        `⏳ Merging pull request <code>${state.owner}/${state.repo} #${state.pullNumber}</code>...`,
        { parse_mode: 'HTML' }
      );

      // 3. Execute merge
      const result = await mergePullRequest(state.owner, state.repo, state.pullNumber, creds.token);

      await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});

      await ctx.replyWithHTML(
        `🎉 <b>Pull Request Merged Successfully!</b>\n\n` +
        `• <b>Repo:</b> <code>${state.owner}/${state.repo}</code>\n` +
        `• <b>PR:</b> <code>#${state.pullNumber}</code>\n` +
        `• <b>Merged by:</b> @${creds.username}\n\n` +
        `💬 <i>Message: ${result.message || 'PR Merged.'}</i>`
      );
    } catch (err) {
      console.error('Merge PR failed:', err);
      if (statusMsg) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
      }
      ctx.reply(`❌ Failed to merge Pull Request:\n${err.message}`);
    }
  });

  // Action Handler: Close PR
  bot.action('execute_pr_close', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state || state.type !== 'pr') return ctx.answerCbQuery('Session expired.');

    // 1. Check Authentication
    const creds = getUserCredentials(chatId);
    if (!creds) {
      try {
        const url = getOAuthUrl(chatId);
        return ctx.replyWithHTML(
          `🔑 <b>Authentication Required</b>\n\n` +
          `To close pull requests, you must connect your GitHub account:\n\n` +
          `<a href="${url}">👉 Connect GitHub Account</a>\n\n` +
          `Once connected, click the <b>🔴 Close PR</b> button again.`,
          { disable_web_page_preview: true }
        );
      } catch (err) {
        return ctx.reply(`❌ OAuth configuration missing: ${err.message}`);
      }
    }

    ctx.answerCbQuery('Checking close permissions...');
    userSessions.delete(chatId); // Clear session

    let statusMsg;
    try {
      statusMsg = await ctx.reply('⏳ Fetching Pull Request information...', { parse_mode: 'HTML' });

      // Fetch details to check if the user is the author
      const details = await fetchPullRequestDetails(state.owner, state.repo, state.pullNumber, creds.token);

      // 2. Verify Close permission
      // User is allowed to close if they have write access OR if they are the original author of the PR
      const hasWriteAccess = await checkCollaboratorPermission(state.owner, state.repo, creds.username, creds.token);
      const isAuthor = creds.username.toLowerCase() === details.author.toLowerCase();

      if (!hasWriteAccess && !isAuthor) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
        return ctx.replyWithHTML(
          `❌ <b>Permission Denied</b>\n\n` +
          `GitHub user <b>@${creds.username}</b> is not authorized to close PR <code>#${state.pullNumber}</code>.\n` +
          `You must either be the author of the pull request (<b>@${details.author}</b>) or have write access to the repository.`
        );
      }

      await ctx.telegram.editMessageText(
        chatId,
        statusMsg.message_id,
        null,
        `⏳ Closing pull request <code>${state.owner}/${state.repo} #${state.pullNumber}</code>...`,
        { parse_mode: 'HTML' }
      );

      // 3. Execute Close
      await closePullRequest(state.owner, state.repo, state.pullNumber, creds.token);

      await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});

      await ctx.replyWithHTML(
        `🔴 <b>Pull Request Closed!</b>\n\n` +
        `• <b>Repo:</b> <code>${state.owner}/${state.repo}</code>\n` +
        `• <b>PR:</b> <code>#${state.pullNumber}</code>\n` +
        `• <b>Closed by:</b> @${creds.username}`
      );
    } catch (err) {
      console.error('Close PR failed:', err);
      if (statusMsg) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
      }
      ctx.reply(`❌ Failed to close Pull Request:\n${err.message}`);
    }
  });

  // Action Handler: Run PR Review
  bot.action('execute_pr_review', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state || state.type !== 'pr') return ctx.answerCbQuery('Session expired.');

    // Use OAuth token if user is logged in, otherwise fallback to bot owner GITHUB_TOKEN
    const creds = getUserCredentials(chatId);
    const tokenToUse = creds ? creds.token : null;

    userSessions.delete(chatId); // Clear session
    ctx.answerCbQuery('Starting PR analysis...');

    let statusMsg;
    try {
      statusMsg = await ctx.reply('⏳ <b>Step [1/2]:</b> Fetching Pull Request metadata and diff from GitHub...', { parse_mode: 'HTML' });

      // Fetch details and diff using correct credentials
      const prDetails = await fetchPullRequestDetails(state.owner, state.repo, state.pullNumber, tokenToUse);
      const prDiff = await fetchPullRequestDiff(state.owner, state.repo, state.pullNumber, tokenToUse);

      if (!prDiff || prDiff.trim() === '') {
        throw new Error('The pull request diff is empty or cannot be fetched.');
      }

      await ctx.telegram.editMessageText(
        chatId,
        statusMsg.message_id,
        null,
        '⏳ <b>Step [2/2]:</b> Analyzing changes and compiling review using Gemini AI...',
        { parse_mode: 'HTML' }
      );

      // Perform analysis
      const reviewReport = await analyzePullRequest(prDetails, prDiff, state.mode);

      // Write report to temporary file
      const tempDir = path.resolve(__dirname, '..', 'temp');
      await fs.ensureDir(tempDir);
      const reportFilePath = path.join(tempDir, `pr-review-${state.owner}-${state.repo}-${state.pullNumber}-${Date.now()}.md`);
      await fs.outputFile(reportFilePath, reviewReport);

      await ctx.telegram.editMessageText(
        chatId,
        statusMsg.message_id,
        null,
        '📤 Sending results to Telegram...',
        { parse_mode: 'HTML' }
      );

      const modeTitle = {
        review: 'Code Quality Review',
        describe: 'PR Description & Changelog',
        improve: 'Refactor Recommendations',
        security_audit: 'Security Audit & Secret Scan',
        all: 'All-in-one Audit'
      }[state.mode] || 'PR Audit';

      await ctx.replyWithDocument(
        { source: reportFilePath },
        {
          caption: `🤖 <b>Gemini PR Review Agent</b>\n` +
            `• Repo: <code>${state.owner}/${state.repo}</code>\n` +
            `• PR: <code>#${state.pullNumber}</code>\n` +
            `• Mode: <b>${modeTitle}</b>\n` +
            `• PR Title: <i>${escapeHtml(prDetails.title)}</i>`,
          parse_mode: 'HTML'
        }
      );

      await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});

      await ctx.replyWithHTML(
        `✅ <b>PR Review completed!</b>\n\n` +
        `The full report markdown file has been delivered to your chat. Open it to read your code audit.`
      );

      // Clean up temp report file
      fs.remove(reportFilePath).catch((e) => console.error('Cleanup PR report file error:', e));

    } catch (err) {
      console.error('PR Review process failed:', err);
      if (statusMsg) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
      }
      ctx.reply(`❌ Failed to review Pull Request:\n${err.message}`);
    }
  });

  // Action Handler: Run Repo Packaging
  bot.action('execute_pack', async (ctx) => {
    const chatId = ctx.chat?.id;
    const state = userSessions.get(chatId);
    if (!state) return ctx.answerCbQuery('Session expired.');

    userSessions.delete(chatId); // Clear session
    ctx.answerCbQuery('Starting build...');

    let statusMsg;
    try {
      statusMsg = await ctx.reply('⏳ <b>Step [1/2]:</b> Cloning and packing repository using Repomix...', { parse_mode: 'HTML' });
      
      // Step 1: Pack the repo
      const packStats = await packRepository(state.url, {
        style: state.style,
        branch: state.branch
      });

      const repoName = state.url.split('/').pop().replace(/\.git$/, '') || 'Repository';

      let reportFilePath = null;
      let analysisSummaryText = '';

      // Step 2: Audit with Gemini if selected
      if (state.analyze) {
        await ctx.telegram.editMessageText(
          chatId,
          statusMsg.message_id,
          null,
          '⏳ <b>Step [2/2]:</b> Analyzing codebase structure & vulnerabilities with Gemini AI...',
          { parse_mode: 'HTML' }
        );

        try {
          const markdownReport = await analyzeRepository(packStats.outputPath, repoName);
          
          // Write report to markdown file to send as a document
          const reportDir = path.resolve(__dirname, '..', 'temp');
          reportFilePath = path.join(reportDir, `analysis-report-${packStats.sessionId}.md`);
          await fs.outputFile(reportFilePath, markdownReport);
          
          // Prepare brief inline overview
          analysisSummaryText = `\n\n📊 <b>AI Analysis completed!</b> Included is the full structural audit report.`;
        } catch (aiErr) {
          console.error('AI Analysis failed:', aiErr);
          analysisSummaryText = `\n\n⚠️ <b>AI Analysis failed:</b> ${escapeHtml(aiErr.message)}\nOnly the packed repomix file is generated.`;
        }
      }

      // Step 3: Send files to user
      await ctx.telegram.editMessageText(
        chatId,
        statusMsg.message_id,
        null,
        '📤 Sending results to Telegram...',
        { parse_mode: 'HTML' }
      );

      const filesToSend = [];
      
      // Add repomix output file
      filesToSend.push({
        media: { source: packStats.outputPath },
        type: 'document',
        caption: `📦 <b>Repomix Codebase Bundle</b>\n` +
          `• Files packed: ${packStats.totalFiles}\n` +
          `• Tokens count: ${packStats.totalTokens.toLocaleString()}\n` +
          `• Size chars: ${packStats.totalChars.toLocaleString()}`,
        parse_mode: 'HTML'
      });

      // Add analysis report file if created
      if (reportFilePath && fs.existsSync(reportFilePath)) {
        filesToSend.push({
          media: { source: reportFilePath },
          type: 'document',
          caption: `🤖 <b>Gemini Code Quality & Security Audit Report</b>`,
          parse_mode: 'HTML'
        });
      }

      // Send files
      if (filesToSend.length === 1) {
        await ctx.replyWithHTML(filesToSend[0].caption);
        await ctx.replyWithDocument(filesToSend[0].media);
      } else if (filesToSend.length > 1) {
        await ctx.replyWithMediaGroup(filesToSend);
      }

      // Delete status message and send confirmation
      await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
      
      await ctx.replyWithHTML(
        `✅ <b>Success!</b> Repository successfully packed.\n\n` +
        `• <b>Files processed:</b> ${packStats.totalFiles}\n` +
        `• <b>Tokens counted:</b> ${packStats.totalTokens.toLocaleString()}` +
        analysisSummaryText
      );

      // Clean up files
      fs.remove(packStats.outputPath).catch((e) => console.error('Cleanup packed file error:', e));
      if (reportFilePath) {
        fs.remove(reportFilePath).catch((e) => console.error('Cleanup report file error:', e));
      }

    } catch (err) {
      console.error('Packaging process failed:', err);
      if (statusMsg) {
        await ctx.telegram.deleteMessage(chatId, statusMsg.message_id).catch(() => {});
      }
      ctx.reply(`❌ Failed to pack repository:\n${err.message}`);
    }
  });

  // Error handling
  bot.catch((err, ctx) => {
    console.error(`Telegram Bot Error for ${ctx.updateType}:`, err);
    ctx.reply('❌ An unexpected error occurred. Please try again.');
  });

  // Launch Bot
  bot.launch()
    .then(() => {
      console.log('🤖 Telegram Bot is running successfully!');
    })
    .catch((err) => {
      console.error('Failed to launch Telegram Bot:', err);
    });

  // Enable graceful stop
  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));

  return bot;
}
