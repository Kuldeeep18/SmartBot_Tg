import express from 'express';
import path from 'path';
import fs from 'fs-extra';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const tokensFilePath = path.resolve(__dirname, '..', 'data', 'tokens.json');

// In-memory cache loaded from tokens.json
let userTokens = {};

// Load tokens from disk on startup
async function loadTokens() {
  try {
    await fs.ensureDir(path.dirname(tokensFilePath));
    if (await fs.pathExists(tokensFilePath)) {
      userTokens = await fs.readJson(tokensFilePath);
      console.log(`Loaded ${Object.keys(userTokens).length} active user authentication sessions.`);
    } else {
      await fs.writeJson(tokensFilePath, {});
    }
  } catch (err) {
    console.error('Failed to load user tokens:', err);
  }
}

// Save tokens to disk
async function saveTokens() {
  try {
    await fs.outputJson(tokensFilePath, userTokens, { spaces: 2 });
  } catch (err) {
    console.error('Failed to save user tokens:', err);
  }
}

// Initialize on load
loadTokens();

/**
 * Generate GitHub OAuth Authorization URL
 * State parameter carries the Telegram chatId so we can associate it back on callback
 */
export function getOAuthUrl(chatId) {
  const clientId = process.env.GITHUB_CLIENT_ID;
  const redirectUrl = process.env.OAUTH_REDIRECT_URL;

  if (!clientId || !redirectUrl) {
    throw new Error('OAuth is not fully configured. GITHUB_CLIENT_ID and OAUTH_REDIRECT_URL must be defined.');
  }

  // Requesting full 'repo' scope to allow write operations (Merge, Close)
  return `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUrl)}&state=${chatId}&scope=repo`;
}

/**
 * Get GitHub access credentials for a Telegram Chat ID
 * @param {number} chatId
 * @returns {object|null} - { token, username }
 */
export function getUserCredentials(chatId) {
  return userTokens[String(chatId)] || null;
}

/**
 * Disconnect a user's GitHub account
 * @param {number} chatId
 */
export async function disconnectUser(chatId) {
  delete userTokens[String(chatId)];
  await saveTokens();
}

/**
 * Initialize OAuth Express Callback Server
 * @param {object} bot - Telegraf bot instance
 */
export function initOAuthServer(bot) {
  const app = express();
  const port = process.env.PORT || 3000;
  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;

  app.get('/oauth/callback', async (req, res) => {
    const { code, state: chatId } = req.query;

    if (!code || !chatId) {
      return res.status(400).send('❌ Authentication failed: Missing authorization code or session state.');
    }

    if (!clientId || !clientSecret) {
      return res.status(500).send('❌ Server configuration error: OAuth credentials missing.');
    }

    try {
      // 1. Exchange temporary code for access token
      console.log(`Exchanging code for token for chatId: ${chatId}`);
      const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          client_id: clientId,
          client_secret: clientSecret,
          code,
          redirect_uri: process.env.OAUTH_REDIRECT_URL
        })
      });

      if (!tokenResponse.ok) {
        throw new Error(`GitHub token exchange returned status ${tokenResponse.status}`);
      }

      const tokenData = await tokenResponse.json();
      const accessToken = tokenData.access_token;

      if (!accessToken) {
        throw new Error(`Failed to exchange code: ${tokenData.error_description || tokenData.error || 'No token returned'}`);
      }

      // 2. Fetch authenticated GitHub user's details
      const userResponse = await fetch('https://api.github.com/user', {
        headers: {
          'User-Agent': 'repomix-telegram-bot',
          'Authorization': `token ${accessToken}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      });

      if (!userResponse.ok) {
        throw new Error(`GitHub user retrieval returned status ${userResponse.status}`);
      }

      const userData = await userResponse.json();
      const githubUsername = userData.login;

      // 3. Save mapping
      userTokens[String(chatId)] = {
        token: accessToken,
        username: githubUsername
      };
      await saveTokens();

      console.log(`Successfully authenticated Telegram Chat ID ${chatId} as GitHub user ${githubUsername}`);

      // 4. Notify user directly in Telegram
      if (bot) {
        await bot.telegram.sendMessage(
          chatId,
          `✅ <b>Authentication Successful!</b>\n\n` +
          `Your Telegram account is now linked to GitHub account: <b>@${githubUsername}</b>.\n` +
          `You can now perform pull request operations (Merge, Close) directly.`,
          { parse_mode: 'HTML' }
        ).catch((err) => console.error('Failed to send Telegram success notification:', err));
      }

      // 5. Render landing page
      res.send(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Authentication Successful</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
              background: #0f172a;
              color: #f8fafc;
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              margin: 0;
            }
            .card {
              background: rgba(30, 41, 59, 0.7);
              backdrop-filter: blur(12px);
              border: 1px solid rgba(255, 255, 255, 0.1);
              padding: 40px;
              border-radius: 16px;
              text-align: center;
              box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
              max-width: 400px;
            }
            h1 { color: #10b981; font-size: 24px; margin-top: 0; }
            p { color: #94a3b8; line-height: 1.6; }
            .button {
              display: inline-block;
              background: #2563eb;
              color: #ffffff;
              padding: 10px 20px;
              border-radius: 8px;
              text-decoration: none;
              font-weight: bold;
              margin-top: 20px;
              transition: background 0.2s;
            }
            .button:hover { background: #1d4ed8; }
          </style>
        </head>
        <body>
          <div class="card">
            <h1>Success!</h1>
            <p>Your GitHub account <b>@${githubUsername}</b> has been linked successfully.</p>
            <p>You can close this tab and return to Telegram to manage your pull requests.</p>
          </div>
        </body>
        </html>
      `);

    } catch (err) {
      console.error('Error during OAuth callback processing:', err);
      res.status(500).send(`❌ Authentication error: ${err.message}`);
    }
  });

  app.listen(port, () => {
    console.log(`🌐 OAuth Web Server listening at http://localhost:${port}`);
  });
}
