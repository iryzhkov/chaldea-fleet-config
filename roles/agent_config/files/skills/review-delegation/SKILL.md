---
name: review-delegation
description: Review cadence, fan-out reviews and delegation patterns for an interactive T3 session carrying out an agreed plan. Use when a milestone is ready for review, when writing a worker or reviewer brief for delegate_task, when deciding whether a review finding blocks, or when splitting work across child tasks.
---

# Reviews and delegation in T3 sessions

This expands the "Interactive work and delegation" section of the shared
instructions; where the two seem to differ, that section wins. Nothing here is a
mandatory ceremony: use these patterns to keep reviews cheap and useful, not to
add steps to the session.

## When to review

Each milestone of an agreed plan gets one round of reviews:

- A main review by a strong model from the provider that did not write the
  change: Sol 6.1 reviews work written by Claude, Opus 5.5 reviews work written
  by Codex.
- Fan-out reviews on the small models of the same two providers, Sonnet 5.5 and
  Luna 6, each given exactly one target area: for example data safety, error
  handling, tests, or a single module. Pick the areas where the milestone is
  most likely to be wrong; two or three are usually enough.
- A critical-review model (Astra or Fable) only for a consequential design
  decision or a disputed finding, never as a routine reviewer.

OpenCode models are not used for reviews. Reviews stay within the brief.

## How to run a round

Call `orchestrator_capabilities` for the current provider and model IDs rather
than guessing them. Start every review round, including re-reviews, as a fresh
`delegate_task` that carries the brief, the prior findings and the responses to
them; do not continue a review through `t3_thread_send` on a child thread. Give
each round its own `clientRequestId`. Launch the main and fan-out reviews of a
round together; a finished child wakes the parent, so never poll.

## What blocks

- A finding blocks only when it cites a requirement from the brief or plan, or
  shows concrete evidence of a defect, and names a location. Anything else is a
  note.
- Findings outside the plan's scope become follow-up notes, not blocking work.
- ACCEPT names the exact commit, reviewed on a clean tree. Any later change
  invalidates it; the next round reviews the new diff.
- At most two fix rounds per milestone. After that the lead decides or asks
  Igor.
- The author may dispute a finding with a reason. Disputes go to a
  critical-review model or to Igor, not to another round of the same reviewer.

## Delegating work

- Workers get no conversation history. Write a self-contained brief: repository
  path, branch and base, allowed files, acceptance checks, rules that apply, and
  what to report.
- Use `isolation: "worktree"` for code changes in a registered T3 project. A
  worktree starts from the parent's local commit; uncommitted edits are not
  copied.
- Split independent parts into parallel children only when their files do not
  overlap.
- Keep fix rounds small: send the blocking findings and the commit, not the
  whole plan again.
- Report implemented, reviewed, merged, deployed and verified as separate
  states. A passing task is not an accepted review, and a merge is not a
  deployment.

## Review brief template

```text
Review <repository> at commit <sha> on branch <branch> (base <base-sha>).
Role: <main reviewer | fan-out reviewer for TARGET AREA only>.
Brief: <plan reference and the milestone's acceptance criteria>.
Scope: <files or diff range>. Out of scope: <what to leave alone>.
Prior findings and responses: <list, or "none, first round">.
Check that the tree is clean at that commit. Do not edit files.
Return the verdict format below and nothing else.
```

## Verdict format

```text
VERDICT: ACCEPT | CHANGES_REQUESTED
COMMIT: <sha reviewed>
FINDINGS:
- severity: blocking | note
  citation: <requirement in the brief or plan, or the defect evidence>
  location: <path:line or symbol>
  finding: <what is wrong and why it matters>
  suggestion: <optional>
```

CHANGES_REQUESTED needs at least one blocking finding. A blocking finding
without a citation or location is treated as a note.
