<!--
  Pointer for non-Claude coding agents (Codex CLI, Google Antigravity — both
  auto-load this file). Claude Code reads CLAUDE.md and ignores this file
  whenever CLAUDE.md exists, so nothing here duplicates into its context.
-->

# Agent instructions

This repo's rules and project memory live under `.claude/`, not here. Before making any change, read:

1. `.claude/rules/core-rules.md` — when to stop and ask, when a plan needs approval first
2. `.claude/rules/coding-guidelines.md` — how code here is written
3. `.claude/rules/workflow.md` — which skill to use for which kind of task
4. `CLAUDE.md` — project overview, commands, gotchas, and the memory map (`.claude/memory/`)

If you were handed a ticket (`.claude/tasks/<feature>/NN-*.md`), it names the specific memory and
pattern entries relevant to it — read those too before coding.

Follow the report and blocker format in `.claude/skills/implementation/SKILL.md`.
