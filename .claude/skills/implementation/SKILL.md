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

## Process

1. Read the ticket file in full, then every entry its **Context to read** section cites.
2. Inspect the current code at the seams the ticket touches.
3. Use `tdd` at the seams the ticket already names. If the ticket doesn't name them and the interface shape itself is in question, that's not yours to resolve — emit a BLOCKED report (see below) instead of picking a seam yourself.
4. Implement the smallest correct change. Avoid unrelated refactoring.
5. Run typechecking regularly, single test files regularly, and the full test suite once at the end.
6. Self-review, then use `ticket-review` (not the built-in `/code-review` — that one hunts bugs;
   `ticket-review` checks this diff against the ticket and this repo's conventions).
7. Flip the ticket's frontmatter to `status: done` (or `blocked`, see below).
8. Commit your work to the current branch.
9. Report back using the template below.

## If you get blocked

Ambiguity in requirements or architecture — not a capability limit — is a decision for the Main
Agent, never yours to make silently. Set the ticket's `status: blocked` and report:

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
