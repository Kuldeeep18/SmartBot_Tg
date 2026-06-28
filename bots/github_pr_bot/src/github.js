import dotenv from 'dotenv';

dotenv.config();

/**
 * Parse a GitHub PR URL and extract owner, repo, and pull number.
 * Supports standard URLs like https://github.com/owner/repo/pull/123
 * and URLs with trailing slashes or subpages like /files.
 * @param {string} prUrl - The GitHub PR URL
 * @returns {object} { owner, repo, pullNumber }
 */
export function parsePullRequestUrl(prUrl) {
  const cleanUrl = prUrl.trim();
  const regex = /^https?:\/\/(?:www\.)?github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)\/pull\/(\d+)/i;
  
  const match = cleanUrl.match(regex);
  if (!match) {
    throw new Error('Invalid GitHub Pull Request URL. Must match format: https://github.com/owner/repo/pull/123');
  }

  return {
    owner: match[1],
    repo: match[2],
    pullNumber: parseInt(match[3], 10)
  };
}

/**
 * Fetch GitHub PR metadata (title, body, author, etc.)
 * @param {string} owner
 * @param {string} repo
 * @param {number} pullNumber
 * @param {string} [customToken] - Optional OAuth token from user
 * @returns {Promise<object>}
 */
export async function fetchPullRequestDetails(owner, repo, pullNumber, customToken = null) {
  const token = customToken || process.env.GITHUB_TOKEN;
  const url = `https://api.github.com/repos/${owner}/${repo}/pulls/${pullNumber}`;
  
  const headers = {
    'User-Agent': 'repomix-telegram-bot',
    'Accept': 'application/vnd.github.v3+json'
  };

  if (token) {
    headers['Authorization'] = `token ${token}`;
  }

  console.log(`Fetching PR details from: ${url}`);
  const response = await fetch(url, { headers });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`GitHub API returned status ${response.status} when fetching PR metadata: ${errorText}`);
  }

  const data = await response.json();
  return {
    title: data.title,
    body: data.body || '',
    author: data.user?.login || 'unknown',
    state: data.state,
    created_at: data.created_at,
    changed_files: data.changed_files,
    additions: data.additions,
    deletions: data.deletions,
    baseBranch: data.base?.ref,
    compareBranch: data.head?.ref
  };
}

/**
 * Fetch raw PR git diff using GitHub REST API.
 * @param {string} owner
 * @param {string} repo
 * @param {number} pullNumber
 * @param {string} [customToken] - Optional OAuth token from user
 * @returns {Promise<string>} - Raw diff text
 */
export async function fetchPullRequestDiff(owner, repo, pullNumber, customToken = null) {
  const token = customToken || process.env.GITHUB_TOKEN;
  const url = `https://api.github.com/repos/${owner}/${repo}/pulls/${pullNumber}`;

  const headers = {
    'User-Agent': 'repomix-telegram-bot',
    'Accept': 'application/vnd.github.v3.diff' // Crucial: gets raw diff format
  };

  if (token) {
    headers['Authorization'] = `token ${token}`;
  }

  console.log(`Fetching PR diff from: ${url}`);
  const response = await fetch(url, { headers });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`GitHub API returned status ${response.status} when fetching PR diff: ${errorText}`);
  }

  const diffText = await response.text();
  return diffText;
}

/**
 * Check if a GitHub user has write/admin permissions on a repository
 * @param {string} owner
 * @param {string} repo
 * @param {string} username
 * @param {string} token - User's OAuth token
 * @returns {Promise<boolean>}
 */
export async function checkCollaboratorPermission(owner, repo, username, token) {
  const url = `https://api.github.com/repos/${owner}/${repo}/collaborators/${username}/permission`;
  
  const headers = {
    'User-Agent': 'repomix-telegram-bot',
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': `token ${token}`
  };

  console.log(`Checking permissions for ${username} on ${owner}/${repo}`);
  const response = await fetch(url, { headers });

  if (!response.ok) {
    if (response.status === 404) {
      // 404 means the user is not even a collaborator/contributor with access
      return false;
    }
    const errorText = await response.text();
    throw new Error(`GitHub API permission check failed: ${errorText}`);
  }

  const data = await response.json();
  const permission = data.permission; // 'admin', 'write', 'read', 'none'
  return permission === 'admin' || permission === 'write';
}

/**
 * Merge a GitHub Pull Request
 * @param {string} owner
 * @param {string} repo
 * @param {number} pullNumber
 * @param {string} token - User's OAuth token
 * @returns {Promise<object>} - Merge status details
 */
export async function mergePullRequest(owner, repo, pullNumber, token) {
  const url = `https://api.github.com/repos/${owner}/${repo}/pulls/${pullNumber}/merge`;

  const headers = {
    'User-Agent': 'repomix-telegram-bot',
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': `token ${token}`,
    'Content-Type': 'application/json'
  };

  console.log(`Merging PR ${owner}/${repo} #${pullNumber}`);
  const response = await fetch(url, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      commit_title: `PR #${pullNumber} Merged via Telegram Bot`,
      merge_method: 'merge'
    })
  });

  const responseText = await response.text();
  let data;
  try {
    data = JSON.parse(responseText);
  } catch {
    data = { message: responseText };
  }

  if (!response.ok) {
    throw new Error(data.message || `Failed to merge PR: HTTP ${response.status}`);
  }

  return data;
}

/**
 * Close a GitHub Pull Request (marks as closed without merging)
 * @param {string} owner
 * @param {string} repo
 * @param {number} pullNumber
 * @param {string} token - User's OAuth token
 * @returns {Promise<object>} - Updated PR status
 */
export async function closePullRequest(owner, repo, pullNumber, token) {
  const url = `https://api.github.com/repos/${owner}/${repo}/pulls/${pullNumber}`;

  const headers = {
    'User-Agent': 'repomix-telegram-bot',
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': `token ${token}`,
    'Content-Type': 'application/json'
  };

  console.log(`Closing PR ${owner}/${repo} #${pullNumber}`);
  const response = await fetch(url, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({
      state: 'closed'
    })
  });

  const responseText = await response.text();
  let data;
  try {
    data = JSON.parse(responseText);
  } catch {
    data = { message: responseText };
  }

  if (!response.ok) {
    throw new Error(data.message || `Failed to close PR: HTTP ${response.status}`);
  }

  return data;
}
