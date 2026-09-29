---
name: to-tickets
description: Break a plan, spec, or the current conversation into a set of tickets under .claude/tasks/<feature-slug>/, each declaring its blocking edges and a complexity rating, then delegate each unblocked one.
disable-model-invocation: true
source: https://github.com/mattpocock/skills
source_skill: skills/engineering/to-tickets
status: adapted
license: MIT
---

# To Tickets

Break a plan, spec, or conversation into a set of **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a spec path) as an argument, read its full body.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Respect active decisions in `.claude/memory/decisions.md` and conventions in `.claude/memory/patterns.md` for the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the work into **tracer bullet** tickets.

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

Give each ticket a **complexity** rating — `trivial | small | medium | large` — based on how many files/seams it touches, whether it introduces a new interface/abstraction, whether it's a wide-refactor batch, and how much ambiguity remains. This drives which model implements it later (`.claude/routing.json`); it is your estimate, not a fact, so the user reviews it in the next step.

<sizing-rules>

Dispatching a ticket isn't free: a Claude subagent and an external CLI process (Codex, Antigravity,
or anything else) both start with zero context, so every dispatch re-pays the cost of loading the
surrounding code. Size tickets with that cost in mind:

- A ticket rated `trivial` isn't worth a dispatch at all: mark it for **direct implementation**
  instead of writing it up as a ticket file (see step 6).
- Two adjacent `trivial`/`small` tickets **connected by a `depends_on` edge** (one blocks the other)
  should usually be merged into one ticket — the delegate would otherwise re-read the same
  surrounding code twice for two halves of one idea.
- Two `trivial`/`small` tickets that are **independent** (no edge between them, both eligible for
  the frontier on their own) stay separate even though they're both small — merging them would
  block dispatching them to different agents in parallel.

</sizing-rules>

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each ticket, show:

- **Title**: short descriptive name
- **Blocked by**: which other tickets (if any) must complete first
- **What it delivers**: the end-to-end behaviour this ticket makes work
- **Complexity**: your rating, one line of justification

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?
- Does any complexity rating look wrong?

Iterate until the user approves the breakdown.

### 5. Write the ticket files

Write one file per ticket under `.claude/tasks/<feature-slug>/NN-slug.md`, numbered from `01` in dependency order (blockers first). One ticket per file, never a single combined file.

<ticket-template>

```
---
id: <NN>
title: <Ticket title>
status: ready
depends_on: [<ids this ticket is blocked by; omit or leave empty if none>]
assigned_to: null
complexity: trivial|small|medium|large
plan_rounds: 0
impl_rounds: 0
---

**What to build:** <the end-to-end behaviour this ticket makes work, from the user's perspective,
not a layer-by-layer implementation list>

**Context to read:** <specific `.claude/memory/decisions.md` / `patterns.md` / `troubleshooting.md`
entries relevant to THIS ticket — cite the section, not just "read memory">

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

</ticket-template>

`status` moves through `ready → plan-pending → plan-approved → in-progress → done` for a `medium`/
`large` ticket dispatched to a delegate (`blocked` at any point it stops for a decision); `trivial`
tickets never get a file at all, and `small` tickets skip straight from `ready` to `in-progress` —
see step 6.

A `## Plan History` section is *not* part of the initial template — `watch-delegate` appends it
(creating it on first use) only for a `medium`/`large` ticket dispatched to a **Claude subagent**:
approved plans, `BLOCKED` reports, self-corrections, and DONE-verification verdicts all land there
(see `.claude/skills/watch-delegate/SKILL.md` and `.claude/skills/implementation/SKILL.md`). A ticket
dispatched to an external CLI never needs this section — that history already lives durably in its
own `NN-slug.exchange.json`, which survives archiving; a Claude subagent's session and plan-review
conversation don't survive anything, so the ticket file is the only durable record for those.

Avoid specific file paths or code snippets beyond what's needed to locate the seam: they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype.

Do not modify `.claude/tasks/<feature-slug>/SPEC.md` — tickets reference it, they don't rewrite it.

### 6. Write the skeleton and tests, then delegate

Tickets rated `trivial` are not dispatched — implement them directly right now, using `tdd` for the
change itself, and skip the rest of this step (per the `<sizing-rules>` in step 3, they were never
written up as a ticket file to begin with).

The **frontier** is every other ticket whose `depends_on` are all `done` (for a purely linear chain,
that's ticket `01`). Do the following for a ticket once it's about to be dispatched, not upfront for
the whole chain — a skeleton written too early goes stale if an earlier ticket changes the code's
shape.

**One ticket at a time, start to finish (6.1 through 6.4), even when several tickets are
simultaneously in the frontier** (no dependency edge between them, both eligible right now). Never
bundle more than one ticket's version of 6.1's question into a single UI turn — e.g. one multi-select
form asking who implements `#01`/`#02`/`#03` all at once — finish one ticket's dispatch before
starting the next one's 6.1. This matters specifically because of the lock in 6.1: a lock written
while handling an earlier ticket must make every later ticket in the same frontier skip the question
entirely, and a batched ask can't know that lock exists yet at the point it's built — asking all
three at once is exactly how you end up re-asking (and re-answering) the same lock decision three
times instead of once.

#### 6.1 Ask who implements it

Every dispatched ticket gets implemented by an agent — never by the real user coding it by hand.
Read `delegates` from `.claude/routing.json` (fall back to `.claude/routing.example.json`'s
default, `["claude"]`, if the project has no `routing.json` yet):

- **Only `"claude"` listed** → no other coding CLI is configured for this project. Skip the
  question — there's nothing to choose between — say so in one line, and go straight to 6.2.
- **At least one external CLI listed too** → check `delegate_lock` in `.claude/routing.json` for
  this feature-slug before asking anything:
  - **Already locked** (`delegate_lock["<feature-slug>"] == "external_cli"`) → say so in one line
    ("this feature is locked to an external CLI, dispatching without asking") and go straight to
    6.2, treating this ticket the same as if the real user had just answered (2)/(3) below. Never
    re-ask while the lock holds — that's what locking it in means.
  - **Not locked** → ask, and wait for the answer. Never infer it from what an earlier *unlocked*
    ticket's answer was (answering "external CLI, just this once" for ticket 01 is not consent to
    keep using it for ticket 02) — offer exactly these three choices every time, worded to not be
    confusable with each other:
    - **(1) A Claude subagent, just this ticket** — you (the Main Agent) spawn it in this session
      right now. The next ticket in the frontier asks again from scratch.
    - **(2) An external coding CLI, just this ticket** — run by the real user in their own
      terminal (Codex, Antigravity, opencode, Cursor's CLI, or anything else — the exchange
      protocol in 6.4 only watches for `turn: "delegate"`, it doesn't care which CLI acts on it,
      so don't ask which one). The next ticket in the frontier asks again from scratch.
    - **(3) An external coding CLI, locked in for every remaining ticket in this feature** — same
      dispatch as (2) for this ticket, but also write `delegate_lock["<feature-slug>"]:
      "external_cli"` to `.claude/routing.json` now (atomically — temp file, then rename). No more
      asking for this feature until it's unlocked (below) or archived.

Both branches continue to 6.2.

**Unlocking mid-feature**: if the real user says, in plain language, that they want to change who
implements the rest of this feature (e.g. "switch back to Claude", "ask me again for this one"),
remove that feature's `delegate_lock` entry from `.claude/routing.json` right away and ask the
three-choice question again for the next ticket — no special command syntax needed, this is an
ordinary conversational request like any other.

**Re-running `to-tickets`** for a feature that already has tickets (cutting more, or resuming after
a break) always starts this question fresh: remove any existing `delegate_lock` entry for that
feature-slug first, even if it was locked before, then follow the flow above as if this were the
first ticket. A lock from a previous cutting pass is not consent for this one either.

**On archive**: once `update-memory-bank` archives a feature's tickets to `.claude/tasks/_archive/`,
remove that feature's `delegate_lock` entry too — it only means anything for a feature still being
dispatched, and a stale entry could otherwise silently skip the question if the feature-slug is
ever reused.

If the real user edits `delegates` later — adding or dropping a CLI — that takes effect starting
with the next ticket dispatched; no need to reinstall or re-run `/init-agent`.

If that edit drops every external CLI from `delegates` (leaving only `"claude"`, or emptying the
list), clear every `delegate_lock` entry right then, even for features the user didn't mention —
a lock with no external CLI left to point to is stale, and leaving it in place means it silently
re-applies, unasked, if an external CLI is ever added back while that feature is still open.

#### 6.2 Write the skeleton and its tests

Before dispatching, write the seam-level skeleton this ticket needs directly into the codebase:

- A seam isn't only a brand-new function that needs a stub — wiring a new call or branch into an
  *existing* function (no separate stub possible there) is a seam too, whenever it changes
  observable behavior. For a wiring seam you still write its test now, red against today's code —
  there's no stub to point at, the test itself is what pins the contract — and its file still goes
  in `test_paths`.

  **Exception**: if a correct test for that seam can only be written with a fact that doesn't exist
  yet — not "what should this return" but something like exact call ordering, timing, or sequencing
  inside the existing function that only becomes fixed once someone actually wires the code (e.g. a
  test needs to know whether a new RNG-consuming call lands before or after an existing one, to seed
  it deterministically) — don't guess. See "Delegate-authored tests" under step 6.4's exchange
  protocol for how that case is handled instead.
- One skeleton function per seam you've decided needs a test for this ticket — never a skeleton for
  an internal helper; factoring inside a seam is the delegate's own call. This is also what keeps a
  ticket from decomposing into too many tiny functions: the seam count already drives the ticket's
  `complexity`, so it's the only thing allowed to grow the skeleton.
- Each skeleton function gets a full signature (parameters, types, return type). Add a docstring
  only if the name, signature, and the test's name don't already make the behavior obvious:
  0–1 lines for `trivial`/`small` seams, up to ~3 lines for `medium`/`large` seams, naming only the
  acceptance criterion it satisfies — never restating what the test itself already says. The body is
  a stub (`TODO` / `NotImplementedError` / your language's equivalent).
- Write the test(s) for each seam now, following `tdd`'s seam and test-quality rules. Because you
  (the Main Agent) are writing these, the seam is already agreed — the delegate never has to
  reconfirm it, closing the gap `tdd` describes for headless runs. The tests must fail (red) against
  the stub bodies.

Required for every dispatched ticket, `small` included — only the direct-implementation path
(`trivial` tickets, step 6's opening paragraph) skips it.

#### 6.3 Write the first request, then hand off

Your job for this ticket ends at the first dispatch. Everything from here — plan-round negotiation,
verifying a DONE reply, triaging a BLOCKED, retries, escalation — is
`.claude/skills/watch-delegate/SKILL.md`'s job, not yours; see its note on why that content moved
out of this file.

- **`trivial`/`small` ticket** → no plan step. Skip straight to 6.4's implementation dispatch.
- **`medium`/`large` ticket** → set `status: plan-pending` and write the first request as a **plan
  request**, not an implementation request. If this is going through the exchange protocol (an
  external CLI), this first write is also where you set `stage: "plan"` in the exchange file —
  `exchange-check` step 6 branches its own behavior on this field, so a first dispatch that never
  sets it leaves the delegate with no documented case to match:

  > Read the ticket at `.claude/tasks/<feature-slug>/NN-slug.md`, `AGENTS.md`, and the skeleton/tests
  > at `<paths>`. Do not write any implementation code yet. Reply with a plan covering exactly these
  > four parts: (a) your approach, in prose, (b) the files/seams you expect to touch, (c) risks or
  > points you're unsure of, (d) how you'll verify the change. No code in the reply.

#### 6.4 Dispatch, then hand off to `watch-delegate`

- **Claude** → set `assigned_to: claude`, `status: in-progress`, look up its model in
  `.claude/routing.json` (fall back to `.claude/routing.example.json`) by `complexity`, and call the
  `Agent` tool with that model. The prompt is the ticket file content plus the skeleton/test paths
  and, for `medium`/`large` tickets, the plan request from 6.3 — a fresh subagent only needs the
  ticket, the contract, and that request. Point it at `.claude/skills/implementation/SKILL.md`. The
  instant it returns, invoke `watch-delegate` with its reply — there's no Monitor to arm here, the
  call is synchronous.
- **Any other external CLI** (Codex, Antigravity, opencode, Cursor's CLI, or anything else) → set
  `assigned_to` and `status: in-progress`, write the exchange file (`ticket_path`, `stage` from 6.3,
  `skeleton_paths`, `test_paths`, `request` from 6.3, `turn: "delegate"`), then invoke
  `watch-delegate` — it owns arming the Monitor and everything after. **The real user runs the
  delegate CLI themselves, in their own terminal — never spawn it as a subprocess.** Most such CLIs'
  own tool-permission model auto-denies anything they need (network reads, writes outside a narrow
  default, etc.) unless launched with a flag that skips all of their permission prompts; Claude
  Code's own auto-mode classifier denies Claude spawning a process with that flag itself ("Create
  Unsafe Agents"). There is no way around this from inside Claude Code — don't try another tool,
  another quoting trick, or another invocation shape to get the same outcome; ask the real user to
  run it instead.

Mention the routing suggestion for that complexity tier as a hint, not an instruction. If
`.claude/routing.json` has a block for that delegate, its value may still be blank — say so if it
is. If the delegate has no block there at all (e.g. it was added to `delegates` by hand without
one), say that too ("no routing suggestion configured for `<cli>`") instead of silently mentioning
nothing — the real user picks the model themselves either way, but they should know it's missing,
not assume there was never one to give.

Once `watch-delegate` reports a terminal outcome for this ticket (`done`, or `blocked`/escalated),
the ticket(s) it was blocking may join the frontier if it finished `done` — repeat this step for
them, immediately and without waiting to be told, regardless of which delegate handled the ticket
that just finished. If it finished `blocked`/escalated and the real user later re-cuts it via a fresh
`/to-tickets` run, that re-cut naturally reaches this same step 6 again once it's ready to dispatch.
