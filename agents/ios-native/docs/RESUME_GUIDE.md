# Resuming an Interrupted Session — Quick Guide

For when a Claude Code (or Codex) session stops mid-work: tokens/rate limit
ran out, terminal closed, machine rebooted, or the conversation just got too
long.

## 1. Resume the same Claude Code conversation

From `C:\SentinelX` in PowerShell:

```powershell
claude --continue        # reopens the most recent conversation in this folder
claude --resume          # shows a picker of past conversations to choose from
```

- `--continue` (`-c`) is the usual choice — it restores the full conversation
  and Claude picks up where it left off.
- If the session ended because the **5-hour rate limit** ran out, nothing is
  lost: wait for the reset (the limit error message shows the time), then
  `claude --continue`.
- Long sessions auto-compact (older messages get summarised) — that is
  normal and work continues across it. You don't need to do anything.
- Tip: `/rename` a session to something memorable (e.g. `ios-dev-server`)
  so it's easy to spot in the `--resume` picker later.

## 2. Starting a fresh session instead

If `--continue` isn't available or the old conversation is too stale, a fresh
session recovers fast because state lives in files, not the chat:

Paste this as your first message:

> Continue the SentinelX iOS phase. Read `agents/ios-native/docs/STATUS.md`
> (current state + worklog), `agents/ios-native/docs/CODEX_ROADMAP.md` (task
> queue), and `git log --oneline -10`, then pick up the "Next:" item from
> the latest Claude Code worklog entry.

That works because of the conventions we keep:

| Where | What it preserves |
|-------|-------------------|
| `docs/STATUS.md` | Current phase, agent lanes, dated worklog with "Next:" steps |
| `docs/CODEX_ROADMAP.md` | Codex task queue + IN PROGRESS/DONE markers |
| `docs/DECISIONS.md` | Why non-trivial choices were made |
| Git commits (one per task) | Exactly what code landed and when |
| Claude's auto-memory (`~/.claude/projects/...`) | Cross-session project facts — loads automatically |

## 3. Rules that make resuming painless

- **Commit often** — one task = one conventional commit. Uncommitted work is
  the only thing a dead session can lose. If a session is running low, ask
  Claude to "commit what's done and update STATUS.md" before it stops.
- **STATUS.md worklog entries always end with a "Next:" line** — that line is
  the resume point.
- Never let both agents edit the same folder in parallel (current split:
  Claude Code = `server/app/` + `ios/`, Codex = `server/tools/` + tests).

## 4. Codex specifically

Codex re-orients itself from files alone: it is instructed (in `AGENTS.md`)
to read the roadmap and STATUS.md before doing anything, so restarting Codex
is just launching it again in `agents/ios-native/` — no special resume command
needed.
