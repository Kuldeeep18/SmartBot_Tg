import dotenv from 'dotenv';
import { startBot } from './src/bot.js';
import { initOAuthServer } from './src/oauth.js';

// Load configurations
dotenv.config();

console.log('===================================================');
console.log('  REPOMIX TELEGRAM BOT, REPO ANALYZER & PR AGENT   ');
console.log('===================================================');

const botToken = process.env.TELEGRAM_BOT_TOKEN;
const geminiKey = process.env.GEMINI_API_KEY;

if (!geminiKey) {
  console.warn('⚠️  WARNING: GEMINI_API_KEY is not defined in the .env file.');
  console.warn('   AI Analysis reports will not work, but file bundling will still operate.');
} else {
  console.log('✅ Gemini API Key is configured.');
}

// OAuth Client Check
const githubClientId = process.env.GITHUB_CLIENT_ID;
if (!githubClientId) {
  console.warn('⚠️  WARNING: GITHUB_CLIENT_ID is not configured in .env.');
  console.warn('   PR Merge & Close buttons will request login but OAuth callback will fail.');
}

if (!botToken) {
  console.log('\n🔧 STATUS: The bot application is fully built and ready!');
  console.log('🔑 To run it, please edit your ".env" file and paste your Telegram Bot Token under:');
  console.log('   TELEGRAM_BOT_TOKEN=your_token_here');
  console.log('\n🚀 Once the token is added, start the bot by running:\n   npm start\n');
} else {
  console.log('🚀 Initializing Telegram Bot...');
  const bot = startBot(botToken);
  
  // Start OAuth web server alongside Telegram Bot
  if (bot) {
    console.log('🚀 Initializing OAuth callback web server...');
    initOAuthServer(bot);
  }
}
