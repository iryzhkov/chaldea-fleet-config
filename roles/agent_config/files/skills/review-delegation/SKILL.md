---
name: review-delegation
description: Review cadence, fan-out reviews and delegation patterns for an interactive T3 session carrying out an agreed plan. Use when a milestone is ready for review, when writing a worker or reviewer brief for delegate_task, when deciding whether a review finding blocks, or when splitting work across child tasks.
---

# Reviews and delegation in T3 sessions

This expands the "Interactive work and delegation" section of the shared
instructions; where the two seem to differ, that section wins. Builders may launch their own
reviews, but every review must use T3 `delegate_task`.

## When to review

Review the final commit of each milestone of an agreed plan:

- A main review by a strong model from the provider that did not write the
  change: Sol 6.1 reviews work written by Claude, Opus 5.5 reviews work written
  by Codex, subject only to the quota exception below.
- Add at most one narrow fan-out review, only for security- or data-sensitive
  work, with exactly one target area such as data safety or credential handling.
- A critical-review model (Astra or Fable) only for a consequential design
  decision or a disputed finding, or the quota exception below.

OpenCode models are not used for reviews. Reviews stay within the brief. Report
each reviewer's thread ID, model and verdict in the reply and as a PR comment.

## How to run a round

Before each delegation, call `chaldea_route` or `chaldea route --role ROLE` and pass
its `providerInstanceId`, `model` and `options` as the T3 `delegate_task` target.
Use `builder` for main diff reviews, `critical-review` for consequential design or
disputed findings, `bulk-read` for readers and `general` for other work. For reviews,
pass the writer's driver as `authorProvider`, `claudeAgent` or `codex`, or CLI
`--author-provider`, to require the other provider. Honor explicit session model
restrictions. If routing is unavailable, use the CLAUDE.md model roles and
`orchestrator_capabilities` IDs, applying the provider rule and quota exception below.

Start every review round, including re-reviews, as a fresh
`delegate_task` that carries the brief, the prior findings and the responses to
them; do not continue a review through `t3_thread_send` on a child thread. Give
each round its own `clientRequestId`. Launch the main review and any permitted fan-out of a
round together; a finished child wakes the parent, so never poll.

## Quota exception

Cross-provider review remains the default. Only an observed quota stop on the
other provider with a reliable reset more than one hour away at review selection
permits a waiver.
Unknown quota/reset, a reset at most one hour away, routing preference or a
missing recommendation does not qualify. Honor explicit user/model overrides.

Keep a fresh independent context through a new T3 `delegate_task`. Select a more
capable available model at high reasoning; for Sol-authored Codex work, prefer
`gpt-6-astra` with `reasoningEffort=high`. This is a same-provider exception,
not a cross-provider review. Keep normal FATE/role selection otherwise.

Route first with `authorProvider` as usual. If that strict filter has no candidate
under a qualifying stop, record the explicit waiver, then resolve an appropriate
available target and high-effort option from `orchestrator_capabilities`. Do not
weaken the router's filter or change routing code. Record the exception reason,
observed stop and reset timestamps with their evidence, reviewer thread ID,
provider/model/effort and verdict in both the PR comment and checkpoint.
No spending, reset redemption or authentication changes are authorized.

The exact reviewed commit, clean-tree acceptance, citation/location blocking
rule and two-fix-round limit below still apply. Existing reviews on an available
other provider continue; this exception applies to future qualifying stops.

## What blocks

- A finding blocks only when it cites a requirement from the brief or plan, or
  shows concrete evidence of a defect, and names a location. Anything else is a
  note.
- Findings outside the plan's scope become follow-up notes, not blocking work.
- ACCEPT names the exact commit, reviewed on a clean tree. After an accepted
  review, the orchestrator verifies a change of under about 50 lines without
  another review. For larger changes, review the final commit again.
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
- Keep fix rounds focused, while retaining the original brief, prior findings,
  responses and unresolved objections in each new `delegate_task` prompt.
- Report implemented, reviewed, merged, deployed and verified as separate
  states. A passing task is not an accepted review, and a merge is not a
  deployment.

## Review brief template

```text
Review <repository> at commit <sha> on branch <branch> (base <base-sha>).
Role: <main reviewer | fan-out reviewer for TARGET AREA only>.
Brief: <plan reference and the milestone's acceptance criteria>.
Scope: <files or diff range>. Out of scope: <what to leave alone>.
Check two axes separately: repository documented standards and originating issue/spec.
Sources: <standards files/rules>; <issue/spec reference, or unavailable>.
Cite each applicable rule/requirement; do not let one axis mask the other.
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
