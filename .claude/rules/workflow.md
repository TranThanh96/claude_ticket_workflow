# Workflow: which skill, when

Don't force every task through every stage. Pick the row that matches, top to bottom.

| Task | Path |
| --- | --- |
| Trivial (obvious rename, tiny isolated fix) | implement directly → test |
| Bug | `debugging` → fix → test → `ticket-review` → troubleshooting.md if the cause wasn't obvious |
| Small feature | `to-spec` → `implementation` → test → `ticket-review` |
| Large feature / architectural | `grilling` → `to-spec` → `to-tickets` → delegate → `implementation` → test → `ticket-review` → update memory |

- `grilling`: resolve ambiguity before spending a spec on it. Skip for trivial tasks.
- `to-spec`: synthesize the conversation into a spec at `.claude/tasks/<feature-slug>/SPEC.md`. No interview.
- `to-tickets`: break the spec into `.claude/tasks/<feature-slug>/NN-slug.md` tickets, then delegate each
  unblocked one (spawn a Claude subagent, or hand you a command for Codex/Antigravity).
- `implementation`: what a coding agent (Claude subagent, or you running Codex/Antigravity) does with one
  ticket — read it, use `tdd` at agreed seams, implement, report back.
- `ticket-review`: does the diff match the ticket/spec and this repo's conventions? Two axes, run
  separately from the built-in `/code-review` (that one hunts bugs; this one checks conformance).
- `update-memory-bank`: as today, plus archiving a feature's tickets once every one is `done`.

Model per ticket complexity: `.claude/routing.json` (copy from `.claude/routing.example.json`).
