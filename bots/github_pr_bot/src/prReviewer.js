import dotenv from 'dotenv';

dotenv.config();

/**
 * Perform AI analysis on a Pull Request diff.
 * @param {object} prMetadata - Metadata fetched from GitHub API
 * @param {string} prDiff - Raw git diff text
 * @param {string} mode - 'review' | 'describe' | 'improve' | 'all'
 * @returns {Promise<string>} - Markdown formatted review
 */
export async function analyzePullRequest(prMetadata, prDiff, mode = 'review') {
  const apiKeysRaw = process.env.GEMINI_API_KEY;
  if (!apiKeysRaw) {
    throw new Error('Gemini API Key is not configured. Please set GEMINI_API_KEY in the .env file.');
  }
  const apiKeys = apiKeysRaw.split(',').map(k => k.trim()).filter(Boolean);
  if (apiKeys.length === 0) {
    throw new Error('Gemini API Key is not configured. Please set GEMINI_API_KEY in the .env file.');
  }

  // Cap the diff size to prevent payload limit overflow (~500KB limit, which fits ~125K tokens)
  const maxChars = 500 * 1024;
  let diffContent = prDiff;
  if (prDiff.length > maxChars) {
    console.log(`PR diff size is ${prDiff.length} characters. Truncating to first ${maxChars} characters.`);
    diffContent = prDiff.slice(0, maxChars) + '\n\n...[Diff truncated due to size limits]...';
  }

  // Construct context
  const context = `PR Title: ${prMetadata.title}
PR Author: ${prMetadata.author}
PR Description:
${prMetadata.body || '(No description provided)'}

Files Changed Count: ${prMetadata.changed_files} (+${prMetadata.additions} / -${prMetadata.deletions})
Base Branch: ${prMetadata.baseBranch} <-- Compare Branch: ${prMetadata.compareBranch}`;

  // Select Prompt based on mode
  let systemPrompt = '';
  if (mode === 'review') {
    systemPrompt = `You are an expert code reviewer. Review the following Git Pull Request diff and write a structured review report.
Analyze the changes carefully for correctness, style, security, and bugs.

Your report must be structured as follows:

# Pull Request Review Report

## 🔍 Overview & Summary
- Provide a brief summary of the changes introduced and their overall impact on the codebase.

## 🛠️ Code Quality & Architecture
- Review the code style, readability, modularity, naming conventions, and architectural structure.

## 🐛 Bug Detection & Edge Cases
- List any potential logical errors, edge cases not handled, race conditions, memory leaks, or incorrect API usage.

## 🔒 Security Observations
- Note any security risks, vulnerabilities (e.g., SQL injection, XSS, unsafe inputs), exposed configurations, or authentication issues.

## 🏆 Verdict & Recommendations
- Give a final verdict: Approved, Request Changes, or Comment. List 1-3 critical items to address.`;
  } else if (mode === 'describe') {
    systemPrompt = `You are an AI assistant helping developers document their pull requests. Analyze the following Git Pull Request diff and create a detailed PR Description template.

Your description must be structured as follows:

# Pull Request Description

## 📝 Overview
- A concise summary explaining the main goal and high-level changes of this pull request.

## 📂 Detailed Changelog
- Group changes by folder/component.
- For each modified file in the diff, describe *what* was modified and *why* in clear bullet points.

## 📋 Suggested Testing Steps
- Provide a checklist of testing scenarios (both unit testing and manual verification) that the reviewer should perform to validate these changes.`;
  } else if (mode === 'improve') {
    systemPrompt = `You are a Senior Software Architect. Review the following Git Pull Request diff and identify specific locations in the modified files that can be refactored, optimized, or corrected.

For each improvement recommendation, provide:
1. File name and approximate line reference.
2. The reasoning behind the improvement (clarity, performance, security, style, etc.).
3. A clear side-by-side or block code comparison:
   - **Before:** (the code as written in the diff)
   - **After:** (your proposed improved code)

Only suggest improvements that are highly relevant to the modified lines. Do not suggest generic improvements.`;
  } else if (mode === 'security' || mode === 'security_audit') {
    systemPrompt = `You are a Lead Cybersecurity Auditor and DevSecOps Specialist. Perform an in-depth security audit on the following Git Pull Request diff.

Your report must be structured as follows:

# 🔒 Security Audit & Vulnerability Report

## 🛡️ Executive Summary
- A high-level assessment of the security risk posture of this pull request (Risk Rating: Low / Medium / High / Critical).

## 🔑 Credential & Secret Leak Checks
- Audit diffs for hardcoded API keys, OAuth tokens, private keys, passwords, database URLs, or exposed environment variables.

## ⚠️ OWASP & Logic Vulnerabilities
- Check for SQL Injection, XSS, CSRF, Path Traversal, Unsafe Deserialization, Insecure Direct Object References, and missing input sanitization.

## 📦 Dependency & Configuration Risks
- Identify outdated, insecure, or untrusted dependencies added, as well as insecure server/CORS config additions.

## 🛠️ Remediation Guidance
- Concrete step-by-step security fixes for any vulnerabilities identified in the modified files.`;
  } else {
    // default: all-in-one
    systemPrompt = `You are an elite software reviewer and architect. Perform a comprehensive review, description, and improvement audit of the following Git Pull Request diff.

Your output must combine the following sections:

# PR Agent Review Summary

## 📖 description
- Write a 2-sentence overview of the changes.

## 🔍 Review Findings
- **Quality & Style**: Code quality notes.
- **Bugs & Edge Cases**: Potential errors.
- **Security**: Security findings.

## 💡 Code Improvements
- Provide specific refactorings in a Before/After comparison format:
  - **File:** [filename]
  - **Reasoning**: Why change it.
  - **Before/After Comparison**: Show code blocks.

## 🏆 Final Verdict
- Approved, Comment, or Request Changes. List the top priorities.`;
  }

  const prompt = `${systemPrompt}

Here is the PR Context:
--- START PR CONTEXT ---
${context}
--- END PR CONTEXT ---

Here is the Git Diff:
--- START GIT DIFF ---
${diffContent}
--- END GIT DIFF ---`;

  console.log(`Sending PR review request to Gemini (${mode} mode, diff length: ${diffContent.length} chars)...`);

  // Call Gemini API using standard fetch
  const model = 'gemini-2.5-flash';
  let lastError = null;
  let response = null;

  for (const key of apiKeys) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`;
    console.log(`Attempting Gemini API request with key starting with: ${key.slice(0, 8)}...`);
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          contents: [
            {
              parts: [
                {
                  text: prompt
                }
              ]
            }
          ],
          generationConfig: {
            temperature: 0.2,
            topP: 0.95,
            topK: 40,
            maxOutputTokens: 8192,
            responseMimeType: 'text/plain'
          }
        })
      });

      if (response.ok) {
        break;
      } else {
        const errorText = await response.text();
        let parsedError;
        try {
          parsedError = JSON.parse(errorText);
        } catch {
          parsedError = errorText;
        }
        const errMsg = parsedError?.error?.message || errorText;
        console.warn(`Gemini API key starting with ${key.slice(0, 8)} failed: status ${response.status} - ${errMsg}`);
        lastError = new Error(`Gemini API request failed with status ${response.status}: ${errMsg}`);
      }
    } catch (err) {
      console.warn(`Network error with Gemini API key starting with ${key.slice(0, 8)}: ${err.message}`);
      lastError = err;
    }
  }

  if (!response || !response.ok) {
    throw lastError || new Error('All configured Gemini API keys failed.');
  }

  const result = await response.json();
  const reportText = result?.candidates?.[0]?.content?.parts?.[0]?.text;

  if (!reportText) {
    throw new Error('Received empty response from Gemini API.');
  }

  return reportText;
}
