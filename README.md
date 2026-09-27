# claude_ticket_workflow

**Spec-first planning for large features, and tickets you can delegate across Claude, Codex, and Antigravity.**

The [claude_memory_bank](https://github.com/TranThanh96/claude_memory_bank) answers "what
happened before." It has nothing to say about "how do I break a big feature into pieces, or
hand pieces to different coding agents." That's what this repo solves:

```
                         .claude/rules/workflow.md picks the path by task size
  trivial ──────────────────────────────────────────────────► implement → test
  bug     ── debugging ────────────────────────────────────► fix → test → ticket-review
  small   ── to-spec ───────────────────────────────────────► implementation → test → ticket-review
  large   ── grilling → to-spec → to-tickets → delegate ────► implementation → test → ticket-review → update memory
```

`to-tickets` cuts a spec into tickets with `depends_on` edges, and only tickets whose blockers
are all done ever get worked on — that set is the **frontier**:

```
to-tickets writes:   01 (no blockers)   02 (blocked by 01)   03 (blocked by 01)
                            │
                            ▼
       01: trivial? implement it directly, no dispatch at all
       01: otherwise, write its skeleton + tests, then delegate to:
                 Claude subagent | Codex | Antigravity | yourself
                            │
        medium/large: plan → Main Agent reviews (approve / correct / escalate) → implement
        trivial/small: implement straight away
                            │
                       01 → done
                            │
                            ▼
             02 and 03 join the frontier — repeat for each
```

Whoever implements a ticket (`.claude/skills/implementation/SKILL.md`) reports back DONE, BLOCKED,
or PARTIAL; `scripts/tasks_status.py` shows the whole board without opening every file.

**Requirements:** `git`, `python3`, and an existing
[claude_memory_bank](https://github.com/TranThanh96/claude_memory_bank) install in the target
project — these skills read and cite `decisions.md` / `patterns.md` / `troubleshooting.md` there.
Using Claude Code and want both installed together with a guided `/init-agent` command? See
[claude_init_setup](https://github.com/TranThanh96/claude_init_setup).

## When do I need this?

Start with just the memory bank. Add this layer only once you actually hit its problem — every
skill here is one more thing to read, and `grilling` / `to-spec` / `to-tickets` cost real turns
before any code gets written.

| Situation | Add this layer? |
| --- | --- |
| Solo or small team, mostly trivial fixes / bugs / small features | No, the memory bank is enough |
| You plan large or architectural features and want a written spec before code | Yes |
| You split a feature's tickets across Claude, Codex, and/or Antigravity | Yes |
| You want a formal Standards-vs-Spec review per ticket (not just `/code-review`) | Yes |

## Install

```sh
git clone https://github.com/TranThanh96/claude_ticket_workflow.git ~/workspace/claude_ticket_workflow
~/workspace/claude_ticket_workflow/install.sh path/to/project
```

Files that don't exist in the target are copied as-is; existing files are never overwritten. If
the target already has `AGENTS.md`, the template is staged as `AGENTS.md.template` with a merge
prompt for your coding agent.

Then copy `.claude/routing.example.json` to `.claude/routing.json` and fill in the `codex` /
`antigravity` model names once you've actually used them (the `claude` block uses model aliases
and never goes stale).

**Upgrade** an existing install: `install.sh --upgrade path/to/project`. Template-owned files
(the workflow skills, `routing.example.json`, `tasks_status.py`) are replaced with the new
version — unless you have uncommitted changes in them, in which case they're listed and left
alone. `AGENTS.md` is never overwritten, only staged as `.template`.

## The skills

- **`grilling`** — resolve ambiguity before spending a spec on it. Interviews you round by round,
  only asking what's already unblocked.
- **`to-spec`** — synthesizes the conversation into `.claude/tasks/<feature-slug>/SPEC.md`. No interview.
- **`to-tickets`** — cuts the spec into vertical-slice tickets under
  `.claude/tasks/<feature-slug>/NN-slug.md`, each with a `depends_on` list and a `complexity`
  rating. `trivial` tickets are implemented directly, never dispatched; adjacent `trivial`/`small`
  tickets in the same dependency chain get merged. For every other ticket in the frontier, it writes
  the seam-level skeleton and tests first, gets a plan approved for `medium`/`large` tickets, then
  delegates the implementation.
- **`implementation`** — what a coding agent does with one ticket: read it, fill in the given
  skeleton using `tdd` at its pre-written seams, never edit a test, stay inside an approved plan's
  scope, report DONE / BLOCKED / PARTIAL.
- **`tdd`** / **`debugging`** — the red-green loop and the disciplined bug-diagnosis loop used
  inside `implementation`.
- **`ticket-review`** — two parallel sub-agents check the diff against this repo's conventions
  (**Standards**) and against the ticket (**Spec**) — different from the built-in `/code-review`,
  which hunts bugs and doesn't know what the ticket asked for.

Delegation picks a coding agent per ticket:

- **Claude** — a subagent is spawned in-session immediately, model chosen from `.claude/routing.json`
  by the ticket's complexity.
- **Codex** / **Google Antigravity** — you're given a ready-to-run command
  (`codex exec "..."` / `antigravity run "..."`). Both read `AGENTS.md` at the repo root on their own,
  so they pick up this project's rules without being told twice.

For `medium`/`large` tickets, the delegate replies with a short plan (approach, files/seams, risks,
test strategy) before writing any code; the Main Agent approves it, corrects it, or — only when the
plan depends on something never actually decided — brings it to you. Every dispatch (plan, a
correction round, or the final implementation) is a fresh, stateless run: nobody resumes a prior
Codex/Antigravity session, since neither CLI's own context compaction is reliable enough to trust
with what the delegate needs to remember.

`scripts/tasks_status.py` shows ticket status without opening every file. "update memory" (from
the memory-bank layer) archives a feature's tickets to `.claude/tasks/_archive/` once every ticket
in it is `done`.

`AGENTS.md` is inert for Claude Code itself: it reads `CLAUDE.md` and ignores `AGENTS.md` whenever
`CLAUDE.md` exists (which it does once the memory bank is installed), so there's no double-context
cost to shipping both.

## What's included

```
AGENTS.md                               # pointer for non-Claude coding agents (Codex, Antigravity)
.claude/routing.example.json            # complexity → model per coding agent (copy to routing.json)
.claude/rules/workflow.md               # always loaded: which skill for which kind of task
.claude/skills/grilling/                # resolve ambiguity before spending a spec on it
.claude/skills/to-spec/                 # conversation → .claude/tasks/<feature>/SPEC.md
.claude/skills/to-tickets/               # spec → tickets, then delegate each unblocked one
.claude/skills/implementation/          # what a coding agent does with one ticket
.claude/skills/tdd/                     # red-green-refactor loop
.claude/skills/debugging/               # disciplined bug-diagnosis loop
.claude/skills/ticket-review/           # Standards + Spec review of a diff against its ticket
.claude/tasks/                          # <feature-slug>/SPEC.md + NN-slug.md tickets, _archive/ once done
scripts/tasks_status.py                 # ticket status table + depends_on validation
```

## Developing this template

```
python3 -m unittest discover -s tests -v   # end-to-end tests, stdlib only
```

CI runs on Linux and macOS (bash 3.2) with Python 3.9 and 3.12.

## Credits

The `grilling`, `to-spec`, `to-tickets`, `tdd`, `debugging`, and `ticket-review` skills are
adapted from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT); each carries
`source`/`source_skill` frontmatter naming the exact upstream file it started from.
