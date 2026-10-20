---
name: roadmap-executor
description: >-
  Execute an adopted roadmap or plan of record as its current primary
  orchestrator, including resuming or taking over an explicit orchestration
  handoff. Not for delegated implementer, reviewer, reader, operator or spike
  tasks unless their brief assigns orchestration ownership; planning or
  reshaping an uncertain roadmap uses roadmap-planner.
---

# Execute the adopted roadmap

Use this only while you own orchestration: you choose milestones, integrate work
and keep the checkpoint. A delegated worker follows its brief and loads the skills
its own task needs, even when the parent uses this skill. Continue routine work
inside Igor's agreement without asking again.

## Keep a small working set

- Start from the execution checkpoint or handoff: current outcome and decisions,
  state, source refs, active task/thread/run/wait/PR and CI IDs, blockers and next
  action. For Chaldea the checkpoint is
  `tooling/handoffs/chaldea-execution-checkpoint.md` and the plan of record
  `tooling/plans/chaldea-rebuild-plan-2026-10-16.md` in Jocasta. Use current
  revisions, not old transcript summaries.
- Read the plan sections, decisions and findings the next action depends on.
  Linked PRs, reviews, job logs and audits are immutable evidence; open one when a
  decision needs it, not to rebuild history.
- Fetch a full document only when needed, as before every Jocasta update: fetch
  it in full, reconcile and write with `--if-revision N`
  (`~/.config/agents/jocasta.md`), then work from its operative part rather than
  printing it all. Never overwrite a concurrent update.
- Measure context in bytes or tokens, not lines. Project tool output to the fields
  you need, use scoped reads, and read one channel when a tool returns both text
  and structured duplicates.
- Keep plan order, measured-friction reasons, simplicity guardrails and budgets.
  Re-scope overruns with Igor; add capabilities only for a measured need or his
  decision. Recorded decisions are binding, not review debate topics.

## Select work

At kickoff, resume, audit nodes and before choosing the next milestone, triage a
bounded set of untriaged review notes: authorized Akasha reads when available,
otherwise linked PR/Jocasta records, reporting the collection gap. Deduplicate
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
outcome. Keep one integration owner and batch related ready changes for final
review and CI. Apply review-delegation's necessity check in the existing review.

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
- Write worker briefs under review-delegation's "Delegating work". Do not tell a
  worker to load this skill or fetch the full plan or checkpoint, and omit lanes
  that are already terminal. You stay the sole integration and checkpoint owner.
- Children wake the parent on completion. Use `watch_pull_request` for CI and
  review events and Chaldea waits for external time/thread dependencies; save
  their IDs and retry keys. Register then yield; never poll, sleep-loop or create
  duplicate watchers.

## Merge and converge within authorization

- Merge only the exact accepted head on a clean tree with required CI green
  and prior findings resolved under review-delegation. Link each PR in T3.
  Report implemented, reviewed, merged, deployed and verified separately.
- Ask Igor before changes to multiple hosts, credentials, homelab or Normandy
  deployments, or UDM/NAS work, unless that exact scope is already authorized.
  Source implementation is not deployment authority. Never expose secrets.
- Load fleet-rollout for authorized deployments; it owns the converge procedure.
  Report verification evidence per host.
- Background long converges in delegated threads, using their completion wake
  or one Chaldea thread wait for a non-child thread. Preserve command, target,
  log and outcome; reconcile a disconnect or reboot before any retry.
- Any host may reboot without breaking the rest. Do not reboot as a routine
  recovery action. Restart T3 only with `chaldea t3 restart` once that command
  exists, within explicit authorization; until then defer and ask Igor.
  Do not substitute a raw service restart.

## Keep the next milestone resumable

- Update the checkpoint at milestones and genuine state changes, not after every
  tool call: current outcome and lanes, exact commits/PRs, review thread
  IDs/models/verdicts, CI, deployment/verification by host, open decisions/risks
  and next action. Link history instead of copying it; keep entries short rather
  than packing long lines. Reconcile adopted decisions and accepted progress into
  the plan of record.
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
Fill from verified evidence, remove unused clauses and unresolved placeholders,
and link detailed logs. Preparing a prompt does not authorize its execution.

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
Continue inside authorization; checkpoint at milestones or a genuine stop.
Report implemented/reviewed/merged/deployed/verified states separately.
```
