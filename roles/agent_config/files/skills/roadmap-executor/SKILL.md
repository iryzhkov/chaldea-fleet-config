---
name: roadmap-executor
description: >-
  Execute an adopted roadmap or plan of record as its current primary
  orchestrator, including resuming or taking over an explicit orchestration
  handoff. Explicitly delegated bounded milestone groups use sub-roadmap-executor;
  ordinary implementer, reviewer, reader, operator and spike tasks follow their
  briefs. Planning or reshaping an uncertain roadmap uses roadmap-planner.
---

# Execute the adopted roadmap

Use this while you own root orchestration: global priorities, shared interfaces,
cross-group integration, authority and the global checkpoint. Explicitly assigned
bounded milestone groups use sub-roadmap-executor; ordinary workers follow their
briefs and task skills.

Pursue the assigned outcome across milestones until observable acceptance, explicit
stop or cancellation, an agreed budget limit, or a true blocker with no useful
authorized ready work left. A milestone, review, merge, context compaction or
monitor registration is an intermediate state, not permission to end execution.

Record existing authority once: scope, accepted outcomes, repositories, integration,
merge/publication and deployment rights, targets, cost limits and exclusions. Carry
it through resumes and handoffs without reauthorization, including approved operator
or multi-host scope. Ask only about concrete new authority or material unresolved
direction. A plan does not grant rights missing from the conversation or assignment.

## Retain native executor ownership

At authorized kickoff on an already active, unsnoozed thread, inspect lifecycle and
prior pin through available native state or public projection. If verified unpinned,
use `t3_thread_organize` with `action: "pin"`. Record the prior pin, resulting
`pinnedAt`, executor ownership and cleanup owner in the existing checkpoint.
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

## Keep a small working set

- Start with the current checkpoint's outcome, execution status, authority,
  active ownership, blockers and next action. A stopped roadmap stays stopped;
  delayed notifications do not authorize continuation. Use the exact plan and
  checkpoint references from the launch assignment or current handoff. If missing,
  resolve that dependency without guessing a project's roadmap.
- Read only the plan sections and evidence needed for the next decision.
  Reuse skills and references already read while their version and applicability
  remain valid; reload when they change or missing context requires it.
- Fetch the full current document before every Jocasta update, reconcile and use
  WebMCP `if_revision` under `~/.config/agents/jocasta.md`. Full fetch is required
  for safe editing; printing the full body into context is not.
- Project tool results to needed fields and use one response channel when text
  and structured content duplicate each other. Scope catalog/schema discovery
  to the capability needed; keep raw logs on disk and read relevant windows.
  Preserve IDs, errors and evidence required for the decision.
- Keep each fact in its owning document: plan for outcome, decisions and strategy;
  checkpoint for current execution state; linked receipts for detailed evidence.
  Do not copy the same completed history into all three.
- Keep plan order, measured-friction reasons, simplicity guardrails and budgets.
  Re-scope overruns with Igor; add capabilities only for a measured need or his
  decision. Recorded decisions are binding, not review debate topics.

## Select work

Continue the next ready adopted milestone. Triage a bounded review backlog only
for material new findings that could change the current decision or at adopted
audit nodes, not for every notification, resume or milestone transition. Use
authorized Akasha reads when available, otherwise linked PR/Jocasta records and
report the collection gap. Deduplicate
underlying issues, keep exact reviewed heads, task/thread IDs, models,
citations/locations and links, revalidate against current code, and rank by roadmap
fit, concrete benefit/risk, effort and dependencies. Record each disposition and the
adopted work's link in the existing checkpoint or backlog, with the last triage
reference so history is not reread. Notes do not reopen accepted reviews or block a
milestone by default. New milestones, out-of-scope work, large cost,
security/credential changes or multi-host work need separate authority when not
already authorized. No polling, cron or new tracking database.

## Follow the adopted plan

Carry out the plan's milestones, lanes, test and deployment strategy and audit
nodes; do not rediscover the method at each step. Revise the strategy only when
evidence changes it; reshaping milestones or settling new unknowns uses
roadmap-planner. Source, review and merge are intermediate states of an observable
outcome. Keep one root owner for cross-group integration; explicitly bounded
sub-executors own integration within their assigned groups. Batch related ready
changes for final review and CI. Apply review-delegation's necessity check in the
existing review.

Reuse exact accepted reviews and passing checks rather than repeating them; add
tests only for changed behavior. Measure source-to-useful-result time from retained
evidence, separating overlapping work, queue/setup, tests, review, CI, integration
fixes and deployment waits. Address routine measured friction within authorization
without waiting for an audit. Diagnose repeated failures rather than retrying the
same repair or weakening verification.

## Decide without stalling the roadmap

Adopt reasonable, evidence-backed audit recommendations and routine plan adjustments
within the agreed outcome, scope, authority and cost. Record the decision and reason
in the plan/checkpoint and continue; do not request approval for each adoption.

For a significant change of direction or a choice needing Igor, identify the latest
safe decision point: what depends on the answer, what remains useful either way,
and where further work would commit to an unapproved outcome or exceed authority.
Ask once with a concrete recommendation and tradeoff, then continue independent
lanes and bounded investigation or reversible preparation within existing scope.
Do not expand the assignment just to stay busy. Stop only affected work at its safe
boundary; end the execution turn when no useful authorized independent work remains,
with the exact decision, evidence and resumable state checkpointed. Silence, a deadline
or an audit recommendation never grants permission. Existing safety blockers and
source/review/deployment gates remain binding.

## Delegate and follow work

- Route each delegation under the shared "Interactive work and delegation"
  instructions, calling FATE before every `delegate_task`. review-delegation owns
  review pairs, fallbacks, the quota exception and brief templates; builders'
  compliant final-commit reviews count and are not repeated.
- Write ordinary worker briefs under review-delegation's "Delegating work". Do
  not tell ordinary workers to load executor skills or fetch the full plan or
  checkpoint; omit terminal lanes. For a related milestone group, explicitly
  assign the sub-executor role and use sub-roadmap-executor's brief. Give it a
  separate branch/worktree, local checkpoint and only the relevant plan excerpt.
  Name its integration, merge and deployment rights or reserve them to the root.
  It advances routine milestones without parent approval; you retain the global
  checkpoint, interfaces, authority and cross-group integration.
- Use native `delegate_task` completion and `watch_pull_request` for their actual
  child and PR dependencies. PR checks, comments and conflicts can wake; merge
  ends the watch silently. After a CI wake, perform your own authorized merge
  and continue, or retain an owner and recovery action for an external merge.
  Registration is not completion. Continue independent ready work before yielding.
  Never poll, add duplicate monitors, dummy children or fake recurring schedules.
- On official T3 0.1.0, do not substitute external Chaldea time/thread wakes for
  executor dependencies requiring Stop preservation. Pinning does not guard
  external message admission. Follow Chaldea's documented client/cancellation
  limits; preserve historical guarded payloads fail-closed, never strip or replay
  them. If no required native wake exists, record the exact gap, owner and next
  authorized recovery rather than promise guaranteed continuation or add a fork,
  client release, wrapper, store or daemon.
- Before yielding, checkpoint each dependency's owner, task/PR/wait ID and retry
  key, exact source revision, expected wake, next action, recovery deadline and
  recovery action. A deadline prompts diagnosis of that dependency and continued
  independent work; it proves neither success nor delivery. Reconcile child failure
  or CI failure against its exact source, then fix or reassign within authority.
  On a wake, reconcile the authoritative outcome once; ignore duplicate wakes
  already handled. Recover uncertain operations before retrying mutations.
- Follow Chaldea's recovery guidance for missing or failed wakes. Runtime delivery
  reliability remains unqualified; a retained deadline does not itself create a
  continuation wake. Preserve recovery ownership rather than adding another watcher.
  Quota pauses retain the assignment and IDs; resume from their authoritative state.
- Propagate root stop/cancellation to every active child, including sub-executors
  and their workers. Cancel unresolved waits/watchers where supported, reconcile
  in-flight effects and record any cancellation still pending. Explicit stop wins
  over late notifications; none may silently resume stopped work.

## Merge and converge within authorization

- Merge only the exact accepted head on a clean tree with required CI green
  and prior findings resolved under review-delegation. Link each PR in T3.
  Report implemented, reviewed, merged, deployed and verified separately.
- Ask Igor before changes to multiple hosts, credentials, homelab or Normandy
  deployments, or UDM/NAS work, unless that exact scope is already authorized.
  Source implementation is not deployment authority. Never expose secrets.
- Load fleet-rollout for authorized deployments; it owns the converge procedure.
  Report verification evidence per host.
- Run long converges in native delegated tasks and use their completion wake.
  An existing non-child thread has no equivalent native completion dependency;
  retain its owner, exact gap and next authorized recovery instead of substituting
  an external wake requiring Stop preservation. Preserve command, target, log
  and outcome; reconcile a disconnect or reboot before any retry.
- Any host may reboot without breaking the rest. Do not reboot as a routine
  recovery action. `chaldea t3 restart` exists; inspect installed help and host
  capability when needed. Command presence grants no restart authority. Use it
  only within explicit authorization; otherwise defer the restart to the root
  or Igor. Do not substitute a raw service restart.

## Keep the next milestone resumable

- Replace obsolete checkpoint state at milestones and genuine state changes,
  not after every tool call. Keep one current account of outcome/status,
  authority and safety constraints, active owners and task/run/wait IDs, exact
  source/PR/review/CI references, per-host deployed and verified state,
  unresolved findings and next action. Explicitly record none where ownership
  is released. Never leave superseded "active" or "pending" entries underneath
  a new summary.
- Aim for roughly 1,000 to 2,000 words for the operative checkpoint, a soft
  target rather than a gate. Preserve all live IDs, permissions, recovery
  obligations and unresolved risks even when more space is needed. Jocasta
  revisions preserve old state; link an exact prior revision or durable receipt
  before removing detail still needed as evidence. Keep ordinary spacing and
  readable sentences instead of compressing words together.
- Reconcile outcome or strategy changes into the plan; keep routine task/CI
  transitions in the checkpoint. A completed review or job usually needs its
  result, exact source and durable evidence link, not its full log or history.
- Keep a short friction log in the checkpoint or its linked Jocasta document:
  action attempted, observed failure/delay, impact and evidence. Record actual
  tool use, missing consumers, test flakes and review rounds, not speculation.
- Run the plan's audit nodes and track due status under chaldea-audit. Record
  routine adoptions directly. For choices needing Igor, follow the safe decision
  boundary above and preserve progress on independent authorized work.
- End the execution session with a Jocasta handoff for the next orchestrator
  whose literal first line is "Load the roadmap-executor skill first." Include
  exact plan/checkpoint/audit references, active task/thread/run/wait IDs,
  repository branches and commits, PRs/CI/reviews, permissions, blockers and the
  next concrete action.

## Orchestration handoff / kickoff template

For the next orchestrator only; worker and reviewer briefs use review-delegation.
Fill from the current checkpoint and link exact evidence; do not create another
copy of the execution history. Remove unused clauses and unresolved placeholders.
Keep execution status and stop instructions explicit. Preparing a prompt does
not authorize its execution.

```text
Load the roadmap-executor skill first.
Execute <plan@revision> toward <authorized outcome>; checkpoint: <reference>.
First milestone: <observable outcome and acceptance>; then <next step>.
Source: <repo/worktree, branch, exact commit>; map: <verified paths/symbols>.
Inputs/prerequisites: <briefs, artifacts, dependencies and current state>.
Allowed edits/invariants: <scope>; external actions: <existing permissions>.
Checks: <exact commands and expected behavior>; evidence: <durable locations>.
Reviews: <accepted commit, reviewer threads/models/verdicts, open findings>.
In flight: <task/thread/run/wait IDs, PRs and CI>; blockers/risks: <facts>.
Next action: <one concrete action>; budget/boundary: <agreed limit if any>.
Authority: <scope, targets, costs, integration/merge/deploy rights and exclusions>.
Dependencies: <owner, ID, expected wake, source, next action, recovery deadline/action>.
Pin: <prior state, executor-owned pinnedAt or gap, cleanup owner; carry on handoff>.
Continue across milestones until acceptance, explicit stop, agreed budget or no ready work.
Checkpoint at milestones or a genuine stop; late wakes never override cancellation.
Report implemented/reviewed/merged/deployed/verified states separately.
```
