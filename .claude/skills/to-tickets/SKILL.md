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

#### 6.3 For `medium`/`large` tickets: get a plan before code

`trivial`/`small` tickets skip straight to 6.4. For `medium`/`large` tickets, set
`status: plan-pending` and dispatch a **plan request**, not an implementation request:

> Read the ticket at `.claude/tasks/<feature-slug>/NN-slug.md`, `AGENTS.md`, and the skeleton/tests
> at `<paths>`. Do not write any implementation code yet. Reply with a plan covering exactly these
> four parts: (a) your approach, in prose, (b) the files/seams you expect to touch, (c) risks or
> points you're unsure of, (d) how you'll verify the change. No code in the reply.

Review the reply against `SPEC.md`, `decisions.md`, `patterns.md`, and the ticket itself, and sort
any problem into exactly one bucket:

| Bucket | What it means | What you do | Counts toward the round budget? |
| --- | --- | --- | --- |
| **Ungrounded** | The plan assumes something that appears nowhere in the project's knowledge | Escalate to the real user now — this is a decision nobody has made yet | No |
| **Factual inconsistency** | The plan contradicts something already known (current code, a recorded decision, another `done` ticket) | Correct it directly in your reply, ask for a revised plan | Yes |
| **Approach/quality** | The plan is grounded but you judge a different approach is better | Explain why, ask for a revised plan | Yes |
| **Incomplete** | The plan is missing one of its four required parts | Ask for the missing part | No |

Increment the ticket's `plan_rounds` for every round that counts. At `plan_rounds: 3`, the next
"factual inconsistency" or "approach" disagreement escalates to the real user instead of another
round — summarize both positions rather than looping further.

**An escalation can hand back a new fact, not just a decision.** If the real user's answer settles
something concrete that constrains testable behavior (a threshold, a format, a specific rule) and
the tests written in 6.2 don't already verify it, update or add to those tests now — via `tdd`,
still at the seam level, still red against the current stub — before the plan can be marked
approved. The delegate's only feedback loop is the tests it was given and can never edit; a fact
that never enters them is a fact the delegate has no way to be checked against.

Once the plan is acceptable, set `status: plan-approved` and continue to 6.4.

#### 6.4 Dispatch the implementation

- **Claude** → set `assigned_to: claude`, `status: in-progress`, look up its model in
  `.claude/routing.json` (fall back to `.claude/routing.example.json`) by `complexity`, and call the
  `Agent` tool with that model. The prompt is the ticket file content plus the skeleton/test paths
  and, for `medium`/`large` tickets, the approved plan — not the conversation the plan round
  produced; a fresh subagent only needs the ticket, the contract, and the approved plan itself.
  Point it at `.claude/skills/implementation/SKILL.md`.
- **Any other external CLI** (Codex, Antigravity, opencode, Cursor's CLI, or anything else) → set
  `assigned_to` and `status: in-progress`, then dispatch through the exchange protocol below. **The
  real user runs the delegate CLI themselves, in their own terminal — never spawn it as a
  subprocess.** Most such CLIs' own tool-permission model auto-denies anything they need (network
  reads, writes outside a narrow default, etc.) unless launched with a flag that skips all of their
  permission prompts; Claude Code's own auto-mode classifier denies Claude spawning a process with
  that flag itself ("Create Unsafe Agents"). There is no way around this from inside Claude Code —
  don't try another tool, another quoting trick, or another invocation shape to get the same
  outcome; ask the real user to run it instead.

<exchange-protocol>

Each ticket dispatched to an external CLI gets exactly **one** file, next to the ticket, mutated
in place across every round — never a new file per round:

```
.claude/tasks/<feature-slug>/NN-slug.md              # the ticket itself — Claude is the only writer
.claude/tasks/<feature-slug>/NN-slug.exchange.json    # the only channel between Claude and the delegate
```

Unlike a Claude subagent's fresh call, the delegate's own CLI session is **not** reset per round: it
persists across a ticket's plan / plan-correction / implementation rounds (asking the real user to
close and reopen their terminal every round was judged not worth the friction this tier is trying to
remove). It only gets manually reset — the real user runs that CLI's own context-reset command, not
Claude — once a `medium`/`large` ticket reaches a terminal outcome, before the next ticket starts;
this bounds how much of that CLI's own lossy auto-compaction risk can accumulate across a whole
feature, while still accepting it within a single ticket's handful of rounds. `trivial`/`small`
tickets don't need this reset at all.

**Schema** (write atomically — temp file + rename — on both sides, never a partial write the other
side could read mid-flight):

```json
{
  "ticket_path": ".claude/tasks/<feature-slug>/NN-slug.md",
  "stage": "plan | plan_correction | implementation",
  "plan_round": 1,
  "turn": "delegate | claude | none",
  "outcome": null,
  "skeleton_paths": ["..."],
  "test_paths": ["..."],
  "approved_plan": null,
  "request": {},
  "response": null,
  "history": [],
  "updated_at": "<ISO 8601>"
}
```

`outcome` is `null` while a round is in flight; `"done"`, `"blocked"`, or `"escalated"` once the
ticket reaches a terminal state (mirrors the ticket's own `status`, which only Claude ever writes);
`"superseded"` if the ticket gets reassigned away from this delegate mid-flight (see below).
`plan_round` mirrors the ticket's own `plan_rounds` field — Claude is the sole writer of both, so
keep them in sync; the delegate never needs to read the ticket file to know which round it's on.

**Single-writer turn-taking**: only the side named by `turn` may write to the file, ever, and every
write's last act is handing the token to the other side by changing `turn` — to `"claude"` once the
delegate replies, or to `"none"` once `outcome` is set.

**Before writing `turn: "delegate"` for a brand-new dispatch** (never for a correction/continuation of a
ticket already active), run `python3 scripts/exchange_status.py --turn delegate --paths-only` — the
`--paths-only` flag matters: without it, the script always prints *something* (a table header or "no
exchange files found"), so "any output" would misfire on every call. With `--paths-only`, any output
at all means some other ticket is already active — stop, don't write, and treat it as a bug to
investigate (see "Duplicate active ticket" below); never dispatch two at once even by accident.

**Claude writes `request`** — the literal brief for this round (the 4-part plan request from 6.3, or
the implementation brief, including "never edit test_paths, report BLOCKED instead" and, when
`approved_plan` is set, "stay within its declared files/seams, report BLOCKED before leaving them")
— sets `turn: "delegate"`, and arms a `Monitor` watching this exact file path (e.g.
`inotifywait -m --format '%e %f' <path>` on Linux, or `fswatch <path>` on macOS) so the delegate's
reply is caught automatically, re-arming it if it expires (30-minute cap) before the delegate replies.

**Claude cannot start the delegate itself** (see the note above `<exchange-protocol>`) — tell the
real user to run the delegate's `exchange-check` skill/slash-command in its own terminal (no
argument needed: it finds its own pending file via the same `exchange_status.py --turn delegate
--paths-only`).

**The delegate reads `request`, does the round's work, and writes `response`** matching one of:

- Plan round: `{"type": "plan", "approach": str, "files_seams": [str], "risks": str, "test_strategy": str}`
- Implementation round: `{"type": "report", "status": "DONE"|"BLOCKED"|"PARTIAL", "summary": str, "files_changed": [str], "blocked_reason": str|null}`

then sets `turn: "claude"`. It never touches the ticket `.md` or commits anything — only Claude does
either, once it reads a terminal `response`.

**On the Monitor's notification**, Claude reads `response`:

- Missing, or fails to parse against its schema → treat it as a crash, never assume success. Flip
  the ticket to `status: blocked` and escalate to the real user with whatever's available — don't
  try to repair or continue from the exchange file's now-unreliable state yourself; the real user
  decides whether to fix the file and retry, or supersede the ticket (see below).
- Plan reply → the same 4-bucket review as 6.3, and the same rule for what counts toward the
  `plan_round` budget of 3:
  - **Ungrounded**, or a **Factual/Approach** disagreement once the budget is already spent →
    escalate now instead of another round: append the closed round to `history`, `outcome:
    "escalated"`, `turn: "none"`, flip the ticket to `status: blocked`, and bring both positions to
    the real user.
  - **Factual inconsistency** or **Approach/quality** (budget not yet spent) → append the closed
    round to `history`, bump `plan_round` (both here and on the ticket — this is the only bucket
    that counts toward the budget), write a new `request` (the correction), `turn: "delegate"` — a
    fresh Monitor cycle.
  - **Incomplete** → append the closed round to `history`, write a new `request` asking for the
    missing part, `turn: "delegate"` — do **not** bump `plan_round`; 6.3 explicitly excludes this
    bucket from the budget.
  - **Acceptable** → `stage: "implementation"`, write `approved_plan` (the plan text itself, spelled
    out — the delegate's own session may have compacted it away by now), a new `request` (the
    implementation brief), `turn: "delegate"`.
- Implementation reply `DONE` → append to `history`, `outcome: "done"`, `turn: "none"`; flip the
  ticket's `status: done` and commit — Claude's job now, never the delegate's. Continue immediately
  to whatever tickets this one was blocking (see the note at the end of this step) — no need to wait
  for the real user to say so.
- `BLOCKED` → append to `history`, `outcome: "blocked"`, `turn: "none"`; flip the ticket to `status:
  blocked`, escalate to the real user.
- `PARTIAL` → treat like a correction round: append to `history`, a new `request`, `turn: "delegate"`.

**Reassigning a ticket away from the delegate mid-flight** (the real user decides to implement it
themselves, or hand it to someone else, before a terminal outcome): append the current round to
`history`, set `outcome: "superseded"`, `turn: "none"` — *before* changing `assigned_to`. A dangling
`turn: "delegate"` on an abandoned ticket is exactly what the pre-dispatch check above exists to catch.

**Duplicate active ticket** (`exchange_status.py --turn delegate` or `--turn claude` ever returns more
than one file): this should be structurally impossible under the sequential, one-ticket-at-a-time
model this protocol assumes — treat it as a bug, not a race to resolve by picking one. Whichever
side notices first stops and reports it to the real user without acting on either file; only the
real user (or Claude, once told) decides which one is stale and corrects it.

The `NN-slug.exchange.json` file travels with the ticket when a completed feature is archived to
`.claude/tasks/_archive/` — it's part of the ticket's record, not scratch space to clean up on its
own.

</exchange-protocol>

Mention the routing suggestion for that complexity tier as a hint, not an instruction. If
`.claude/routing.json` has a block for that delegate, its value may still be blank — say so if it
is. If the delegate has no block there at all (e.g. it was added to `delegates` by hand without
one), say that too ("no routing suggestion configured for `<cli>`") instead of silently mentioning
nothing — the real user picks the model themselves either way, but they should know it's missing,
not assume there was never one to give.

Once a ticket completes (a Claude subagent returns, or the exchange protocol reaches `outcome:
"done"`), the ticket(s) it was blocking may join the frontier — repeat this step for them,
immediately and without waiting to be told, regardless of which delegate handled the ticket that
just finished.
