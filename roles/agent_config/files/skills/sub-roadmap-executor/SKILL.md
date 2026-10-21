---
name: sub-roadmap-executor
description: >-
  Execute an explicitly delegated related milestone group with local orchestration
  and a local checkpoint under a root roadmap executor. Not for ordinary builder,
  reviewer, reader, operator or spike briefs, or for global roadmap ownership.
---

# Execute a bounded milestone group

Use only when the root explicitly assigns this role. Read the relevant plan excerpt,
acceptance criteria and exact evidence links in the brief, not the full global plan
or checkpoint. The root owns global priorities, interfaces, authority, the global
checkpoint and cross-group integration. You own the assigned milestones, internal
sequencing, separate branch/worktree, local checkpoint, tests and reviews.

Proceed between routine milestones without parent approval until the group's
observable acceptance, explicit stop, agreed budget limit or a blocker with no useful
authorized ready work left. Milestone/review completion and monitor registration
are intermediate states. Preserve assigned authority across turns; integration,
merge, publication and deployment rights must be explicit or remain with the root.
Do not infer global authority from this role.

## Retain native executor ownership

At authorized kickoff on an already active, unsnoozed thread, inspect lifecycle and
prior pin through available native state or public projection. If verified unpinned,
use `t3_thread_organize` with `action: "pin"`. Record the prior pin, resulting
`pinnedAt`, executor ownership and cleanup owner in the existing local checkpoint.
`t3_thread_read` may omit pin metadata; never invent fields or ownership. If prior
or owned state cannot be verified, record the gap and retain cleanup responsibility
rather than blindly pinning or unpinning.

Pinning excludes automatic idle and merged-PR settlement; it is neither a keepalive
nor permission. At final completion or explicit stop, remove only an executor-owned
pin whose current value still matches the recorded `pinnedAt`. Preserve preexisting
user pins and later user changes. Carry ownership through handoff. Never pin,
unsettle or resume stopped, settled, archived or snoozed work from a late wake.
Use Stop/cancel to cancel the assignment and children. Manual Settle only organizes
thread state; native child completion may reopen it. Do not treat manual Settle as
cancellation or promise that native callbacks preserve it. An original Stop or user
cancellation still wins.

## Execute and retain local state

- Make reversible implementation choices and routine fixes within the brief.
  Keep ownership and interface commitments explicit. Escalate material direction,
  new authority, cross-group conflicts or budget overruns to the root, who alone
  asks Igor. Continue useful independent authorized work while an answer is pending.
- Use Huyang for repository reads/edits and Chaldea for builds/tests. Follow
  review-delegation for worker briefs, review routing and exact-source acceptance.
  Delegate nested builders/reviewers only if the live runtime supports it. If
  unsupported, do permitted implementation yourself and send the root exact briefs
  for dispatch, preserving unresolved checks/reviews as dependencies. Continue ready
  work; do not invent child IDs or replace T3 with a separate scheduler.
- Do not delegate another sub-executor by default. Any further layer needs an
  explicit root assignment and supported runtime.
- Keep a separate local checkpoint with outcomes, authority, current source,
  task/review/CI evidence, blockers and next action. Do not concurrently edit the
  root's global checkpoint. Send milestone results and interface changes to the
  root's assigned report destination.
- Use native `delegate_task` completion and `watch_pull_request` for actual child
  and PR dependencies. Checks/comments/conflicts can wake; PR merge ends the watch
  silently. Perform your own authorized merge after the CI wake and continue, or
  retain an owner and recovery action for an external merge. Registration is not
  completion. No polling, duplicate monitors, dummy children or fake schedules.
- On official T3 0.1.0, do not substitute external Chaldea time/thread wakes for
  executor dependencies requiring Stop preservation. Pinning is no message
  admission guard. Preserve historical guarded payloads fail-closed, never strip
  or replay them. Follow Chaldea's client/cancellation limits; if a required native
  wake is unavailable, report the exact gap, owner and next authorized recovery
  to the root. Do not promise guaranteed continuation or add a fork, client release,
  wrapper, store or daemon.
- Yield only when useful independent ready work is exhausted. Retain each dependency's
  owner, task/PR/wait ID and retry key, source revision, expected wake, next action,
  recovery deadline and action. Reconcile authoritative status once on a wake and
  ignore already handled duplicates. Diagnose child/CI failures before retrying.
  Chaldea describes uncertain outcomes and missing-wake recovery; a deadline neither
  creates a continuation nor proves success, an answer or permission. Runtime wake
  reliability remains unqualified.
- Root stop/cancellation overrides late wakes. Stop new work, propagate cancellation
  to every active descendant, cancel unresolved waits/watchers where supported,
  reconcile in-flight operations and report pending cleanup. Never resume stopped
  work from a delayed notification.
- At completion or a genuine stop, return exact head and tree state, implemented/
  reviewed/merged/deployed/verified states, check commands/job IDs/results, evidence
  links, remaining dependencies and the next root action. A local success does not
  prove cross-group integration or deployment.

## Root assignment template

```text
Load sub-roadmap-executor first. Role: bounded sub-executor under <root ID>.
Outcome/milestones: <related group and observable acceptance>.
Plan excerpt: <only relevant decisions, ordering and constraints>; evidence: <exact links>.
Prerequisites/interfaces: <dependencies, owners, contracts and current state>.
Source: <repo, separate worktree/branch, exact base>; owned files: <paths>.
Local checkpoint/report destination: <references>; global checkpoint owner: <root>.
Allowed actions: <implementation, integration, merge/publication/deploy rights or reserved>.
Checks/reviews: <acceptance commands and gates>; budget/stop conditions: <limits>.
Nested delegation: <supported runtime evidence or root-dispatch fallback>; no further layer.
Escalate to root: <direction/authority boundary>; cancellation: <root stop source and cleanup>.
In flight/recovery: <dependency owner, ID, source, expected wake, next action, deadline/action>.
Pin: <prior state, executor-owned pinnedAt or gap, cleanup owner; carry on handoff>.
Advance routine milestones without parent approval; report at milestones or a genuine stop.
```
