---
name: watch-delegate
description: "Supervise one ticket already handed to a delegate (a Claude subagent, or an external CLI via the exchange protocol) from the moment it's dispatched through to a terminal outcome: arm the watch, negotiate plan rounds, verify a DONE reply before accepting it, and triage anything reported as BLOCKED."
disable-model-invocation: true
source_note: "This skill absorbed the <exchange-protocol> section that used to live in to-tickets/SKILL.md, once to-tickets stopped executing it. See to-tickets's own note at the top of its step 6.3/6.4 for why."
---

# Watch Delegate

Supervise **one ticket** for its entire time with a delegate. `to-tickets` hands you a ticket the
moment it writes that ticket's first `request` and either sets `turn: "delegate"` (exchange-protocol)
or calls the `Agent` tool (Claude subagent) — your job starts there and ends the moment the ticket
reaches `status: done`, `status: blocked` (escalated to the real user), or `outcome: "superseded"`.
Once you reach a terminal outcome, report it back to whatever `to-tickets` step invoked you, so it
can move on to the tickets this one was blocking.

## Boundary

You do not author new ticket content from scratch — that's `to-tickets`'s job, per its
`<ticket-template>` (`.claude/skills/to-tickets/SKILL.md`). The one exception is a narrow, grounded
correction (see "Two-tier BLOCKED triage" below): even then, follow `<ticket-template>`'s exact shape,
don't invent your own.

You never spawn a delegate CLI as a subprocess, and you never write anything into an exchange file
except through the single-writer turn-taking rules below.

## Two delivery paths

- **Exchange-protocol (external CLI)** — everything below happens by mutating
  `.claude/tasks/<feature-slug>/NN-slug.exchange.json` in place. See `<exchange-protocol>` for the
  schema and turn-taking rules.
- **Claude subagent** — no exchange file exists. `to-tickets` calls the `Agent` tool pointing at
  `.claude/skills/implementation/SKILL.md`; the instant it returns, apply this skill's
  "Implementation-round handling" below to its Implementation Report **inline, in the same turn** —
  there's nothing to arm a Monitor for, the call is synchronous. Its audit trail lives in the ticket's
  own `## Plan History` section (create it if absent) instead of an exchange file's `history` array —
  append every plan approval, BLOCKED report, self-correction, and DONE-verification verdict there,
  since nothing else durably records what a subagent's own discarded session and conversation showed.

<exchange-protocol>

Each ticket dispatched to an external CLI gets exactly **one** file, next to the ticket, mutated in
place across every round — never a new file per round:

```
.claude/tasks/<feature-slug>/NN-slug.md              # the ticket itself — you are the only writer
.claude/tasks/<feature-slug>/NN-slug.exchange.json    # the only channel between you and the delegate
```

Unlike a Claude subagent's fresh call, the delegate's own CLI session is **not** reset per round: it
persists across a ticket's plan / plan-correction / implementation rounds (asking the real user to
close and reopen their terminal every round was judged not worth the friction this tier is trying to
remove). It only gets manually reset — the real user runs that CLI's own context-reset command, not
you — once a `medium`/`large` ticket reaches a terminal outcome, before the next ticket starts; this
bounds how much of that CLI's own lossy auto-compaction risk can accumulate across a whole feature,
while still accepting it within a single ticket's handful of rounds. `trivial`/`small` tickets don't
need this reset at all.

**Schema** (write atomically — temp file + rename — on both sides, never a partial write the other
side could read mid-flight):

```json
{
  "ticket_path": ".claude/tasks/<feature-slug>/NN-slug.md",
  "stage": "plan | plan_correction | implementation",
  "plan_round": 1,
  "impl_round": 0,
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
ticket reaches a terminal state (mirrors the ticket's own `status`, which only you ever write);
`"superseded"` if the ticket gets reassigned away from this delegate mid-flight (see below).
`plan_round` mirrors the ticket's own `plan_rounds` field; `impl_round` mirrors its `impl_rounds`
field — you're the sole writer of all four, keep each pair in sync. The delegate never needs to read
the ticket file to know which round it's on.

**Single-writer turn-taking**: only the side named by `turn` may write to the file, ever, and every
write's last act is handing the token to the other side by changing `turn` — to `"claude"` once the
delegate replies, or to `"none"` once `outcome` is set.

**Before writing `turn: "delegate"` for a brand-new dispatch** (never for a correction/continuation of
a ticket already active), run `python3 scripts/exchange_status.py --turn delegate --paths-only` — the
`--paths-only` flag matters: without it, the script always prints *something* (a table header or "no
exchange files found"), so "any output" would misfire on every call. With `--paths-only`, any output
at all means some other ticket is already active — stop, don't write, and treat it as a bug to
investigate (see "Duplicate active ticket" below); never dispatch two at once even by accident.

**You write `request`** — the literal brief for this round (the 4-part plan request, a plan
correction, or the implementation brief, including "never edit `test_paths`, report BLOCKED instead"
and, when `approved_plan` is set, "stay within its declared files/seams, report BLOCKED before
leaving them") — set `turn: "delegate"`, and arm a `Monitor` watching this exact file path (e.g.
`inotifywait -m --format '%e %f' <path>` on Linux, or `fswatch <path>` on macOS) so the delegate's
reply is caught automatically, re-arming it if it expires (30-minute cap) before the delegate replies.

**You cannot start the delegate yourself** — tell the real user to run the delegate's `exchange-check`
skill/slash-command in its own terminal (no argument needed: it finds its own pending file via the
same `exchange_status.py --turn delegate --paths-only`).

**The delegate reads `request`, does the round's work, and writes `response`** matching one of:

- Plan round: `{"type": "plan", "approach": str, "files_seams": [str], "risks": str, "test_strategy": str}`
- Implementation round: `{"type": "report", "status": "DONE"|"BLOCKED"|"PARTIAL", "summary": str, "files_changed": [str], "new_tests": [{"path": str, "reason": str}], "blocked_reason": str|null}`

then sets `turn: "claude"`. It never touches the ticket `.md` or commits anything — only you do
either, once you read a terminal `response`.

**Delegate-authored tests**: `new_tests` stays empty for the ordinary case (only `test_paths` files
exist, none of them touched). The one exception is a seam you already approved as
implementation-emergent (see "Plan-round handling" below) — every test written for that seam goes in
`new_tests` with a `reason`, never silently folded into `files_changed`; this is the flag your
independent verification (below) scrutinizes specifically, instead of relying on noticing it in a full
diff. Outside that named exception, the rule is unchanged: never edit a file already in `test_paths`,
and never add a test that wasn't called for by an approved plan's exception.

**Reassigning a ticket away from the delegate mid-flight** (the real user decides to implement it
themselves, or hand it to someone else, before a terminal outcome): append the current round to
`history`, set `outcome: "superseded"`, `turn: "none"` — *before* `to-tickets` changes `assigned_to`. A
dangling `turn: "delegate"` on an abandoned ticket is exactly what the pre-dispatch check above exists
to catch.

**Duplicate active ticket** (`exchange_status.py --turn delegate` or `--turn claude` ever returns more
than one file): this should be structurally impossible under the sequential, one-ticket-at-a-time
model this protocol assumes — treat it as a bug, not a race to resolve by picking one. Whichever side
notices first stops and reports it to the real user without acting on either file; only the real user
(or you, once told) decides which one is stale and corrects it.

The `NN-slug.exchange.json` file travels with the ticket when a completed feature is archived to
`.claude/tasks/_archive/` — it's part of the ticket's record, not scratch space to clean up on its own.

</exchange-protocol>

## Plan-round handling

Applies when `stage` is `"plan"` or `"plan_correction"` (exchange-protocol), or when a Claude subagent
was dispatched with `status: plan-pending` and returns a plan instead of code.

Review the reply against `SPEC.md`, `decisions.md`, `patterns.md`, and the ticket itself, and sort any
problem into exactly one bucket:

| Bucket | What it means | What you do | Counts toward `impl_rounds`/`plan_rounds` budget? |
| --- | --- | --- | --- |
| **Ungrounded** | The plan assumes something that appears nowhere in the project's knowledge | Escalate to the real user now — this is a decision nobody has made yet | No |
| **Factual inconsistency** | The plan contradicts something already known (current code, a recorded decision, another `done` ticket) | Correct it directly in your reply, ask for a revised plan | Yes |
| **Approach/quality** | The plan is grounded but you judge a different approach is better | Explain why, ask for a revised plan | Yes |
| **Incomplete** | The plan is missing one of its four required parts | Ask for the missing part | No |

Increment the ticket's `plan_rounds` (and, for exchange-protocol, the exchange file's `plan_round`)
for every round that counts. At `plan_rounds: 3`, the next "factual inconsistency" or "approach"
disagreement escalates to the real user instead of another round — summarize both positions rather
than looping further.

**A plan whose `test_strategy` proposes writing its own new tests is a Factual inconsistency by
default — don't approve it as-is.** Only `to-tickets` writes tests up front (its step 6.2); a delegate
proposing to add tests itself usually means 6.2 missed a seam, not that the delegate should cover it.
Stop and write that test yourself now — red against current code — add its file to `test_paths` (and
a skeleton to `skeleton_paths` if there's a stub to write), then ask for a revised plan that implements
against what you just pinned, same as any other factual correction.

**Unless the plan can name the specific implementation-emergent fact that blocks writing it now** — a
fact like call ordering or timing that only exists once the code is actually wired, not just an
interface shape nobody has decided yet. If the plan names one and you agree it's real, that's
Acceptable, not a correction: approve the plan as normal, and see "Delegate-authored tests" above for
how that specific test gets written and reviewed once implementation happens.

**An escalation can hand back a new fact, not just a decision.** If the real user's answer settles
something concrete that constrains testable behavior (a threshold, a format, a specific rule) and the
tests written in 6.2 don't already verify it, update or add to those tests now — via `tdd`, still at
the seam level, still red against the current stub — before the plan can be marked approved. The
delegate's only feedback loop is the tests it was given and can never edit; a fact that never enters
them is a fact the delegate has no way to be checked against.

Once the plan is acceptable, set `status: plan-approved`, write `approved_plan` (exchange-protocol) or
append it verbatim to the ticket's `## Plan History` (Claude subagent — the subagent and the
plan-review conversation are both discarded once this returns, so the ticket file is the only durable
record), and move to the implementation round.

## Implementation-round handling (DONE / BLOCKED / PARTIAL)

### On `DONE` — verify independently before accepting

A self-reported PASS is not evidence — the delegate's whole session could have been wrong about it.

1. Re-run the test suite yourself. Don't trust the summary.
2. Diff `files_changed` against `test_paths`: any edit to a file already in `test_paths` is a hard
   violation of "only `to-tickets` writes tests here" — reject it like a `BLOCKED`/`PARTIAL` reply
   (a correction round), don't accept and clean it up yourself.
3. For anything listed in `new_tests`: legitimate only if the plan round already approved that seam's
   implementation-emergent exception — if it wasn't, treat it exactly like an unauthorized edit above.
   If it was, don't just check it passes: **read the test and judge whether it actually exercises the
   claimed behavior** (wrong assertion, wrong target, testing something already covered elsewhere) —
   the same scrutiny you'd apply to a test you wrote yourself. A test that merely passes without
   meaningfully exercising the seam is a correction round, not an accept.
4. `files_changed` that touched a test file with no corresponding `new_tests` entry, on a ticket whose
   approved plan didn't flag an implementation-emergent exception — same hard violation as (2); a
   delegate doesn't get to add a test silently by omitting it from `new_tests`.
5. **Scope adherence**: if an approved plan was in play, diff `files_changed` against its declared
   files/seams. A mismatch with no corresponding BLOCKED report already on record is its own
   violation — treat it as a correction round, don't accept and note it for later. Catching this now,
   before the diff is committed, is cheaper than catching it later in `ticket-review`.

Only once every check above passes: append the round to `history` (or the ticket's `## Plan History`
for a Claude subagent), set `outcome: "done"` / `turn: "none"`, flip the ticket's `status: done`, and
commit — reference the ticket's path in the commit message (e.g. a trailer like
`Ticket: .claude/tasks/<feature-slug>/NN-slug.md`) so `ticket-review` can find it later without asking.
Report the terminal outcome back to `to-tickets` so it can move on to whatever this ticket was blocking
— no need to wait for the real user to say so.

### On `BLOCKED` — two-tier triage

The delegate can't proceed and needs a decision. Don't escalate reflexively — check whether you can
already answer it:

**Tier 1 — grounded.** Read `SPEC.md`, `decisions.md`, and `patterns.md` for the area in question. If
one of them already answers this unambiguously, this isn't a new decision at all — it's the ticket
having drifted from something already settled. Correct the ticket's content yourself, following
`to-tickets`'s `<ticket-template>` exactly (don't invent your own shape), append what you changed and
why to `history` / `## Plan History`, write a corrected `request` for the next round, and continue —
no escalation, nothing for the real user to do here.

**Tier 2 — ungrounded.** None of those documents answer it. This is a genuinely new decision that
nobody has made. Escalate to the real user with the delegate's BLOCKED report as-is (or, for a Claude
subagent, the report it appended to `## Plan History`). Set the ticket's `status: blocked`,
`outcome: "escalated"`, `turn: "none"`. Tell the real user plainly: resolving this may require updating
`SPEC.md` or the ticket's scope, and the safe path is to run `/grill-me` → `/to-spec` → `/to-tickets`
themselves — scoped to just the part that needs to change, not a full re-cut of the feature. Don't
attempt to chain those yourself; each of `to-spec` and `to-tickets` is gated with
`disable-model-invocation: true` for a reason, and `to-spec` specifically needs a real interview
(`grilling`) to produce anything worth trusting — there's no way to fake that from inside this skill.

Once `to-tickets` re-dispatches the corrected ticket (its own step 6 runs again for it), you'll be
handed it fresh, same as any other dispatch.

### On `PARTIAL` — treat as a correction round

Append the round to `history`, write a new `request` addressing what's missing or wrong, `turn:
"delegate"` (or, for a Claude subagent, note it and re-dispatch). Counts toward `impl_rounds`.

## Retry budget: `impl_rounds`

Distinct from `plan_rounds` — this budget is about repeated correction rounds on an *implementation*
reply (a rejected `new_tests` entry, a scope violation, a `PARTIAL`), not about negotiating an
approach. Increment the ticket's `impl_rounds` (and the exchange file's `impl_round`) for every
implementation-round correction. At `impl_rounds: 3`, the next rejection escalates to the real user
instead of another round — same shape as the plan-round budget, summarize what's been tried and why it
keeps failing rather than looping further. A Tier 1 self-correction (above) does **not** count toward
this budget — it's not a disagreement with the delegate, it's you fixing the ticket.

## Audit trail

Every self-correction (Tier 1), BLOCKED escalation (Tier 2), and DONE-verification verdict — accepted
or rejected — gets appended to `history` (exchange-protocol) or the ticket's `## Plan History`
(Claude subagent), including *why* (which check failed, which document grounded a Tier 1 fix). This is
not optional bookkeeping: it's what `ticket-review`'s Spec and Standards axes read before doing their
own pass (see below), and it's the only durable record once a Claude subagent's session and
plan-review conversation are gone.

## Relationship to `ticket-review`

`ticket-review` still runs its own full Standards and Spec review — this skill's accept-time checks
don't replace that, they only narrow its overlapping work. Specifically:

- `ticket-review`'s Standards axis, when checking whether `test_paths`/`new_tests` were handled
  properly, should read this skill's audit trail first and treat what's already recorded as settled —
  it only needs to independently re-derive a verdict for diff content that appeared *after* your
  last DONE-verification (e.g. a manual commit made outside the exchange protocol).
- `ticket-review`'s Spec axis, when checking scope adherence against an approved plan, likewise starts
  from your recorded verdict rather than recomputing the files/seams comparison from scratch.
- Everything else `ticket-review` does — Fowler-smell checks, coding-guideline conformance, "does the
  code actually implement what the ticket asked" beyond scope/test bookkeeping — is fully independent
  of this skill and always runs in full. Passing this skill's accept-time checks is not a substitute
  for `ticket-review`; it only means the ticket wasn't accepted on a lie about its own tests or scope.
