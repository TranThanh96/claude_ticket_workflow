---
name: implementation
description: "Implement one ticket from .claude/tasks/, whether you're a Claude subagent, or a human running Codex/Antigravity yourself."
disable-model-invocation: true
source: https://github.com/mattpocock/skills
source_skill: skills/engineering/implement
status: adapted
license: MIT
note: "The BLOCKED report and Implementation Report templates below are this project's own addition, not from the upstream skill."
---

# Implementation

Implement the work described by one ticket at `.claude/tasks/<feature-slug>/NN-slug.md`.

## Boundary

You are a Coding Agent, not the Main Agent. Do not invoke `grilling`, `to-spec` or `to-tickets`
yourself, even if they're available to you — those decisions belong to whoever created this ticket.
If the ticket or the code is ambiguous, stop and emit a **BLOCKED** report instead of guessing.

If you are not Claude Code (Codex, Antigravity, or anything else), also explicitly read
`.claude/rules/core-rules.md` and `.claude/rules/coding-guidelines.md` now — only Claude Code
auto-loads these.

## Two modes

Check the ticket's `status` before doing anything else:

- **`plan-pending`** — you were dispatched for a **plan request**, not implementation. Read the
  ticket and the skeleton/tests you were pointed at, then reply with a plan only: (a) your approach,
  in prose, (b) the files/seams you expect to touch, (c) risks or points you're unsure of, (d) how
  you'll verify the change. No code in the reply. Stop there — do not touch the codebase.
- **`plan-approved`**, or a `trivial`/`small` ticket with no plan step — implement, following the
  Process below.

## Process

1. Read the ticket file in full, then every entry its **Context to read** section cites.
2. Inspect the current code at the seams the ticket touches. If the ticket was dispatched with a
   skeleton and pre-written tests, they define the seams — don't invent or renegotiate one.
3. Use `tdd` at the seams the ticket already names, filling in the given skeleton bodies. If the
   ticket doesn't name them and the interface shape itself is in question, that's not yours to
   resolve — emit a BLOCKED report (see below) instead of picking a seam yourself.
4. **Never edit a test file you were given.** If you believe one of them is wrong, stop and emit a
   BLOCKED report explaining why — don't work around it and don't change it yourself.
5. **Stay inside the approved plan's declared files/seams and approach.** If you discover mid-task
   that you need to touch something outside that scope, or need a materially different approach,
   stop and emit a BLOCKED report *before* making that change — don't do it first and mention it in
   the final report. Restructuring inside an already-approved seam (helper functions, naming, loop
   style — anything the plan never specified) doesn't need this; only leaving the declared scope
   does.
6. Implement the smallest correct change. Avoid unrelated refactoring.
7. Run typechecking regularly, single test files regularly, and the full test suite once at the end.
8. Self-review, then use `ticket-review` (not the built-in `/code-review` — that one hunts bugs;
   `ticket-review` checks this diff against the ticket and this repo's conventions).
9. Flip the ticket's frontmatter to `status: done` (or `blocked`, see below).
10. Commit your work to the current branch.
11. Report back using the template below.

## If you get blocked

Ambiguity in requirements or architecture, a test you believe is wrong, or a need to leave the
approved plan's scope — not a capability limit — is a decision for the Main Agent, never yours to
make silently. Set the ticket's `status: blocked` and report:

```
# BLOCKED

## Problem
<what's ambiguous or contradictory>

## Why It Matters
<what breaks or gets built wrong if this is guessed at>

## Decision Needed
<the specific question the Main Agent / user must answer>

## Possible Options
<the choices you see, with tradeoffs>

## Technical Observation
<anything you found in the code that bears on the decision>
```

If instead you ran out of capability rather than clarity (e.g. you were run as a lighter model tier
and couldn't complete the ticket), say so explicitly in the report below — the Main Agent may offer
to retry you at a higher tier, but never escalates on your behalf without asking the user first.

## Report back

```
# Implementation Report

## Task
<path to the ticket file>

## Status
DONE | BLOCKED | PARTIAL

## Changes
- ...

## Tests
- ...

## Validation
- lint: PASS | FAIL
- typecheck: PASS | FAIL
- tests: PASS | FAIL

## Files Changed
- ...

## Concerns
- ...

## Follow-up
- ...
```
