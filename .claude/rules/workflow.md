# Workflow: which skill, when

Don't force every task through every stage. Pick the row that matches, top to bottom.

| Task | Path |
| --- | --- |
| Trivial (obvious rename, tiny isolated fix) | implement directly → test |
| Bug | `debugging` → fix → test → `ticket-review` → troubleshooting.md if the cause wasn't obvious |
| Small feature | `to-spec` → `implementation` → test → `ticket-review` |
| Large feature / architectural | `grilling` → `to-spec` → `to-tickets` → `watch-delegate` → `implementation` → test → `ticket-review` → update memory |

- `grilling`: resolve ambiguity before spending a spec on it. Skip for trivial tasks.
- `to-spec`: synthesize the conversation into a spec at `.claude/tasks/<feature-slug>/SPEC.md`. No interview.
- `to-tickets`: break the spec into `.claude/tasks/<feature-slug>/NN-slug.md` tickets, write each one's
  skeleton/tests, and write its first dispatch request (spawn a Claude subagent, or tell you when to
  run an external CLI you run yourself — Codex, Antigravity, or anything else — through its own
  exchange-check step), then hand off to `watch-delegate`.
- `watch-delegate`: supervises one dispatched ticket from that first request through to done/blocked —
  negotiates plan rounds, verifies a DONE reply (reruns tests, checks test legitimacy and scope
  adherence) before accepting it, and triages a BLOCKED report: self-corrects the ticket when the
  answer is already in `SPEC.md`/`decisions.md`/`patterns.md`, otherwise escalates to you.
- `implementation`: what a coding agent (Claude subagent, or you running an external CLI yourself)
  does with one ticket — read it, use `tdd` at agreed seams, implement, report back.
- `ticket-review`: does the diff match the ticket/spec and this repo's conventions? Two axes, run
  separately from the built-in `/code-review` (that one hunts bugs; this one checks conformance).
- `update-memory-bank`: as today, plus archiving a feature's tickets once every one is `done`.

Model per ticket complexity: `.claude/routing.json` (copy from `.claude/routing.example.json`).

Asked to add or drop a delegate CLI (Codex, Antigravity, ...)? Don't guess the format — open
`.claude/routing.json`, read its `_comment`, and follow it: add the CLI's name to the `delegates`
array, and add a matching `{ "trivial": "", "small": "", "medium": "", "large": "" }` block for it
if one doesn't already exist (`antigravity`/`codex` already have one). Takes effect on the next
ticket dispatched — no reinstall, no `/init-agent` re-run.
