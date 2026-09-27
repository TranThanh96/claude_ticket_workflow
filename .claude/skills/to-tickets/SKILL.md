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

Dispatching a ticket isn't free: a Claude subagent and a Codex/Antigravity process both start with
zero context, so every dispatch re-pays the cost of loading the surrounding code. Size tickets with
that cost in mind:

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
tickets never get a file at all, and `small` tickets and self-assigned ones skip straight from
`ready` to `in-progress` — see step 6.

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

Ask the user: **Claude** (subagent) / **Codex** / **Antigravity** / themselves.

- **Themselves** → leave `status: ready`, do nothing further, skip the rest of this step.
- Otherwise, continue to 6.2.

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

Required for every dispatched ticket, `small` included — only the "themselves" and direct-
implementation paths skip it.

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

Once the plan is acceptable, set `status: plan-approved` and continue to 6.4.

#### 6.4 Dispatch the implementation

- **Claude** → set `assigned_to: claude`, `status: in-progress`, look up its model in
  `.claude/routing.json` (fall back to `.claude/routing.example.json`) by `complexity`, and call the
  `Agent` tool with that model. The prompt is the ticket file content plus the skeleton/test paths
  and, for `medium`/`large` tickets, the approved plan — not the conversation the plan round
  produced; a fresh subagent only needs the ticket, the contract, and the approved plan itself.
  Point it at `.claude/skills/implementation/SKILL.md`.
- **Codex** / **Antigravity** → set `assigned_to` and `status: in-progress`, then print the exact
  command for the user to run themselves:
  - Codex: `codex exec "Implement the ticket at .claude/tasks/<feature-slug>/NN-slug.md using the skeleton/tests at <paths>[, following the approved plan: <plan summary>]. Read AGENTS.md first, follow .claude/skills/implementation/SKILL.md, and report back using the Implementation Report format."`
  - Antigravity: `antigravity run "..."` — same content as the Codex command above.

  Every dispatch — the plan request, a correction round, and the final execute — is its own fresh,
  stateless process. Never tell the user to resume or continue a prior Codex/Antigravity session:
  Codex's headless `exec` mode is documented to skip auto-compaction (a long resumed session risks
  crashing outright), and Antigravity's auto-compaction is lossy (it can silently drop a constraint
  the delegate needs). Curate what each fresh process needs yourself — the ticket, the skeleton and
  tests, and, on a correction round, the delegate's last plan plus your specific feedback — rather
  than relying on either CLI's own memory of the conversation.

  Mention the routing suggestion for that complexity tier as a hint, not an instruction
  (`.claude/routing.json` may still be blank for these two agents — say so if it is).

Once a ticket completes (report received, or subagent returns), the ticket(s) it was blocking may
join the frontier — repeat this step for them.
