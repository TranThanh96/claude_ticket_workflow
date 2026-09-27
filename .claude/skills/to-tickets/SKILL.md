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
---

**What to build:** <the end-to-end behaviour this ticket makes work, from the user's perspective,
not a layer-by-layer implementation list>

**Context to read:** <specific `.claude/memory/decisions.md` / `patterns.md` / `troubleshooting.md`
entries relevant to THIS ticket — cite the section, not just "read memory">

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

</ticket-template>

Avoid specific file paths or code snippets beyond what's needed to locate the seam: they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype.

Do not modify `.claude/tasks/<feature-slug>/SPEC.md` — tickets reference it, they don't rewrite it.

### 6. Delegate the frontier

The **frontier** is every ticket whose `depends_on` are all `done` (for a purely linear chain, that's ticket `01`). For each ticket in the frontier, ask the user who implements it: **Claude** (subagent) / **Codex** / **Antigravity** / themselves.

- **Claude** → set that ticket's `assigned_to: claude`, `status: in-progress`, look up its model in `.claude/routing.json` (fall back to `.claude/routing.example.json`) by `complexity`, and immediately call the `Agent` tool with that `model` and the full ticket file content as the prompt — subagents start with no context, which is exactly why the ticket must be self-contained. Point it at `.claude/skills/implementation/SKILL.md` for the process and report format.
- **Codex** / **Antigravity** → set `assigned_to` and `status: in-progress`, then print the exact command for the user to run themselves:
  - Codex: `codex exec "Implement the ticket at .claude/tasks/<feature-slug>/NN-slug.md. Read AGENTS.md first, follow .claude/skills/implementation/SKILL.md, and report back using the Implementation Report format."`
  - Antigravity: `antigravity run "Implement the ticket at .claude/tasks/<feature-slug>/NN-slug.md. Read AGENTS.md first, follow .claude/skills/implementation/SKILL.md, and report back using the Implementation Report format."`

  Mention the routing suggestion for that complexity tier as a hint, not an instruction (`.claude/routing.json` may still be blank for these two agents — say so if it is).
- **Themselves** → leave `status: ready`, do nothing further.

Once a ticket completes (report received, or subagent returns), the ticket(s) it was blocking may join the frontier — repeat this step for them.
