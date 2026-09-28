---
name: exchange-check
description: "Pick up whichever ticket is currently waiting on you in the claude_ticket_workflow exchange protocol, do that round's work, and hand back to the Main Agent. No argument needed."
---

# Exchange Check

The Main Agent (Claude Code, in a separate session) dispatches tickets to you through a single JSON
file per ticket at `.claude/tasks/<feature-slug>/NN-slug.exchange.json`, mutated in place across
rounds — see that repo's `.claude/skills/to-tickets/SKILL.md` (`<exchange-protocol>` section) for the
full schema and turn-taking rules. This skill is the other half: what you do when the real user runs
it, telling you it's your turn.

This file is written for Antigravity's own custom-skill format (frontmatter `name`/`description` →
auto slash command). If you're wiring up a different CLI (Codex, opencode, Cursor's CLI, or
anything else), define an equivalent in whatever custom-command mechanism it supports; if it has
none, the real user pastes `request`'s content directly each round instead of running a command —
the exchange protocol itself doesn't care which CLI is on this side of the file.

## Process

1. Run `python3 scripts/exchange_status.py --turn delegate --paths-only`.
2. **No output, exit code 0** → nothing is waiting on you. Say so and stop.
3. **Exit code 1, or more than one line printed** → this should be structurally impossible (only
   one ticket is ever active at a time). Report exactly what the script printed to the real user
   and stop — do not guess which file to act on, do not pick one.
4. **Exactly one path printed** → read that file. Confirm `turn` is `"delegate"` (it should be, given
   step 1's filter) before doing anything else.
5. Read its `ticket_path` and the ticket file it points to, plus every entry the ticket's
   **Context to read** section cites. Read `skeleton_paths` and `test_paths` — those seams are
   already agreed; don't invent or renegotiate one.
6. Follow `request`'s instructions exactly:
   - `stage: "plan"` or `"plan_correction"` → reply with a plan only — approach, files/seams,
     risks, test strategy. **No code.** Don't touch the codebase.
   - `stage: "implementation"` → implement using the `tdd` skill at the seams `test_paths` already
     name. **Never edit a test file you were given** — if you believe one is wrong, that's a
     BLOCKED reply, not something to fix yourself. Stay inside `approved_plan`'s declared
     files/seams if one is set; leaving that scope is also a BLOCKED reply, made *before* you leave
     it, not after.
7. Write your reply into the file's `response` field, matching exactly one of these shapes:
   - Plan round: `{"type": "plan", "approach": str, "files_seams": [str], "risks": str, "test_strategy": str}`
   - Implementation round: `{"type": "report", "status": "DONE"|"BLOCKED"|"PARTIAL", "summary": str, "files_changed": [str], "blocked_reason": str|null}`
8. Set `turn: "claude"` and `updated_at` to now. Write the whole file atomically (temp file, then
   rename) — never leave a half-written file for the Main Agent to read.
9. Leave `history`, `ticket_path`, `stage`, and `plan_round` exactly as you found them — the Main
   Agent manages all four when it decides what happens next.
10. **Never edit the ticket `.md` file's frontmatter, and never commit anything** — the Main Agent
    does both once it reads your `response`. Your only outputs are the exchange file's `response`
    field and, for an implementation round, the actual code/test changes in the working tree.
11. Exit. The Main Agent is watching this file for the `turn` change — you don't need to announce
    anything else.
