import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs-extra';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper to validate and clean Git remote URLs / shorthands
export function validateRepoUrl(url) {
  const cleanUrl = url.trim();
  
  // Accept standard git/http URLs or user/repo shorthand
  // Simple regex for safety to prevent command injection characters
  const safeRegex = /^[a-zA-Z0-9_.-]+:\/\/[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_./-]*)*$/;
  const shorthandRegex = /^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/;

  if (safeRegex.test(cleanUrl) || shorthandRegex.test(cleanUrl)) {
    return cleanUrl;
  }
  
  throw new Error('Invalid repository URL. Must be a valid Git URL or "user/repo" shorthand.');
}

// Validate branch/ref input for safety
export function validateBranch(branch) {
  if (!branch) return null;
  const cleanBranch = branch.trim();
  const safeBranchRegex = /^[a-zA-Z0-9_./-]+$/;
  if (safeBranchRegex.test(cleanBranch)) {
    return cleanBranch;
  }
  throw new Error('Invalid branch name. Only alphanumeric characters, dashes, dots, slashes, and underscores are allowed.');
}

/**
 * Run repomix on a remote repository
 * @param {string} repoUrl - Target repository URL or shorthand
 * @param {object} options - Format options
 * @param {string} options.style - 'xml' | 'markdown' | 'json' | 'plain'
 * @param {string} options.branch - optional branch/ref name
 * @returns {Promise<object>} - Pack statistics and file path
 */
export async function packRepository(repoUrl, options = {}) {
  const url = validateRepoUrl(repoUrl);
  const style = ['xml', 'markdown', 'json', 'plain'].includes(options.style) ? options.style : 'xml';
  const branch = validateBranch(options.branch);

  const sessionId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const tempDir = path.resolve(__dirname, '..', 'temp');
  await fs.ensureDir(tempDir);

  // Determine output extension based on style
  let ext = 'xml';
  if (style === 'markdown') ext = 'md';
  else if (style === 'json') ext = 'json';
  else if (style === 'plain') ext = 'txt';

  const outputFile = path.join(tempDir, `repomix-output-${sessionId}.${ext}`);
  
  // Construct arguments for repomix
  const args = [
    '-y',
    'repomix@latest',
    '--remote', url,
    '--output', outputFile,
    '--style', style
  ];

  if (branch) {
    args.push('--remote-branch', branch);
  }

  // We do not load the remote repo's config by default for security
  // But we can add it as a flag if needed.

  return new Promise((resolve, reject) => {
    // Determine the npx command based on platform
    const cmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
    
    console.log(`Running: ${cmd} ${args.join(' ')}`);

    const child = spawn(cmd, args, {
      cwd: tempDir,
      shell: true
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      if (code !== 0) {
        // Attempt to clean up just in case
        fs.remove(outputFile).catch(() => {});
        return reject(new Error(`Repomix failed (exit code ${code}).\nStderr: ${stderr || stdout}`));
      }

      // Check if output file actually exists
      if (!fs.existsSync(outputFile)) {
        return reject(new Error('Repomix completed successfully but no output file was created.'));
      }

      // Parse statistics from stdout
      // Typical lines:
      // Total Files: 1,064 files
      // Total Tokens: 1,189,484 tokens
      // Total Chars: 44,78,144 chars
      const fileMatch = stdout.match(/Total Files:\s*([\d,]+)/i);
      const tokenMatch = stdout.match(/Total Tokens:\s*([\d,]+)/i);
      const charMatch = stdout.match(/Total Chars:\s*([\d,]+)/i);
      const securityCheckPassed = stdout.includes('No suspicious files detected') || !stdout.includes('Suspicious files detected');

      // Helper to parse numbers like "1,064" to 1064
      const parseNum = (match) => match ? parseInt(match[1].replace(/,/g, ''), 10) : 0;

      const stats = {
        totalFiles: parseNum(fileMatch),
        totalTokens: parseNum(tokenMatch),
        totalChars: parseNum(charMatch),
        securityPassed: securityCheckPassed,
        outputPath: outputFile,
        sessionId
      };

      resolve(stats);
    });
  });
}
