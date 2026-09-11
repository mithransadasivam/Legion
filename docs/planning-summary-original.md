# Jarvis-Style Personal Assistant — Planning Summary

## Goal
Build a personal AI assistant, inspired by Jarvis/Friday from the Avengers, that can be used across iPhone, iPad, Mac, and a Windows desktop.

## Options considered

### 1. Third-party "skills.md" marketplace (skills.md / Hasna)
- A hosted marketplace of 250+ pre-built skills (icon generation, deep research, video gen, invoices, etc.).
- Installed via CLI (`bun install -g @hasna/skills`) and designed to plug into an existing agent/host — e.g. Claude Code, Cursor, Codex, OpenCode, Antigravity, or any MCP-compatible host.
- Free tier covers public skills; private skills are $10/mo, with additional credits for premium (image/video) runs.
- Not itself a standalone app with a mobile interface — it expects a host application to sit in front of it. MCP-compatible mobile apps are currently scarce, so this doesn't cleanly solve cross-device access on its own.

### 2. Claude's native Skills (via claude.ai account)
- A Skill here is a folder containing a `SKILL.md` file (instructions) plus optional supporting files, uploaded through Settings → Capabilities → Skills.
- Tied to the Claude account, so the same skills are available in the Claude web app and the Claude apps for iOS, iPadOS, Mac, and Windows automatically.
- Included with the existing Claude Pro subscription — no extra cost for writing/uploading your own skills (Anthropic opened Skills, connectors, and file creation up to the free plan as of February 2026, so it isn't even Pro-exclusive).
- Limitation: this style of skill is instruction-only (no embedded executable scripts).

### 3. Claude Code skills (chosen direction)
- Skill folders live locally: `~/.claude/skills/` (personal, all projects on that machine) or `.claude/skills/` (project-specific, can be checked into a repo).
- Can include real executable scripts (Python/bash), not just prose instructions — more capable than claude.ai skills.
- Requires a Claude Pro (or higher) plan to use Claude Code; usage of Claude Code itself is included in that plan.
- Runs on one machine by default, which raised the cross-device question.

## Cross-device access solution: Claude Code Remote Control
- A documented Anthropic feature (available on all plans) that lets an existing local Claude Code session be continued from another device.
- Mechanism: the local session registers with the Anthropic API; connecting from another device routes messages between that device and the local session over a streaming connection.
- Execution and filesystem access stay entirely on the original machine — the phone/tablet/browser is a remote window into that same live session, not a separate copy.
- Access points: the Claude mobile app (iOS/Android) or claude.ai/code in any browser.
- Constraints: one remote session per Claude Code instance at a time; the source machine must stay powered on and connected for remote access to keep working; some reports of dropped connections after long idle periods (this is a newer feature).

## Resulting plan direction
- Designate one always-on machine (likely a Mac) as the "home base" where Claude Code and the Jarvis skill folders live.
- Build and test skills locally on that machine.
- Access and interact with the assistant from iPhone, iPad, or a Windows machine via Claude Code Remote Control, rather than building a separate custom app.

## Not yet decided
- Which specific skill(s) to build first (candidates discussed: daily briefing, personal writing-style drafting, task/project tracker, home automation control via MCP, research assistant).
- Whether/how to give the assistant a distinct "Jarvis" persona (e.g., via custom instructions or a Project) versus using the Claude app as-is.
