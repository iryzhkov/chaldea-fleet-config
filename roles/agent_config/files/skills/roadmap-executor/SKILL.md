---
name: roadmap-executor
description: >-
  Orchestrate an agreed roadmap or plan of record as its current primary
  orchestrator, including resuming or taking over an explicit orchestration
  handoff. Not for delegated implementer, reviewer, reader, operator or spike
  tasks unless their brief assigns orchestration ownership.
---

# Orchestrate the agreed roadmap

Use this only while you own orchestration: you choose milestones, integrate work
and keep the checkpoint. A delegated worker follows its brief and loads the skills
its own task needs, even when the parent uses this skill. Continue routine work
inside Igor's agreement without asking again.

## Resume from a small working set

- Start from the execution checkpoint or handoff: current outcome, state, active
  task/thread/run/wait and CI IDs, blockers and next action. For Chaldea the
  checkpoint is `tooling/handoffs/chaldea-execution-checkpoint.md` and the plan of
  record `tooling/plans/chaldea-rebuild-plan-2026-10-16.md` in Jocasta. Use current
  revisions, not old transcript summaries.
- Read the plan sections, briefs, decisions and audit findings the next action
  depends on. Linked PRs, reviews, job logs and audits are immutable evidence; open
  one when a decision needs it, not to rebuild history every turn.
- Before any Jocasta update, fetch the full current document, reconcile and write
  with `--if-revision N` (`~/.config/agents/jocasta.md`); never overwrite a
  concurrent update.
- Keep plan order, measured-friction reasons, simplicity guardrails and budgets.
  Re-scope overruns with Igor; add capabilities only for a measured need or his
  decision. Recorded decisions are binding, not review debate topics.

## Select work

At kickoff, resume, audit boundaries and before choosing the next milestone, triage a
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

## Check the simplest existing path

Before proposing new machinery or a large estimate, trace the current implementation
and authorized deployment evidence. Compare configuration, version-pin and enrollment
changes first; name the exact unmet requirement before adding a process, account,
state store or publication path. Mark unverified premises as unknown. A budget is a
ceiling, not a target. If evidence contradicts a design assumption, reconcile the plan
before dependent work, preserving Igor's explicit goals and constraints. Apply
review-delegation's necessity check in the existing review.

Define the first milestone by an observable user outcome, including deployed data
when requested; source, review and merge are intermediate states. Keep optional UI or
completeness work separate. Choose PR boundaries with review-delegation's grouping
guidance, keep one integration owner and batch related ready changes for final review
and CI.

When a milestone crosses an uncertain format or data-contract seam, prove it before
deployment with a bounded spike: real producer output through the actual validator,
ingest path or consumer in an isolated agent-a Chaldea job. Production verification
then checks permissions, scheduling and natural delivery, not format discovery.
Trivial or already-proven seams need no spike. A need for extensive new fixtures
should prompt checking the design premise again.

Reuse exact accepted reviews and passing checks rather than repeating them; add tests
only for changed behavior. Measure source-to-useful-result time from retained
evidence, separating overlapping work, queue/setup, tests, review, CI, integration
fixes and deployment waits. Address routine measured friction within authorization
without waiting for an audit. Diagnose repeated failures rather than retrying the
same repair or weakening verification.

## Delegate and follow work

- Route each delegation under the shared "Interactive work and delegation"
  instructions, calling FATE before every `delegate_task`. review-delegation owns
  review pairs, fallbacks, the quota exception and brief templates; builders'
  compliant final-commit reviews count and are not repeated.
- Write worker briefs under review-delegation's "Delegating work": bounded,
  self-contained, carrying the accepted decisions and exact references the task
  needs. Do not tell a worker to load this skill or fetch the full plan or
  checkpoint. You stay the sole integration and checkpoint owner.
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

- After every milestone, update the checkpoint as a working set: current outcome
  and lanes, exact commits/PRs, review thread IDs/models/verdicts, CI,
  deployment/verification by host, open decisions/risks and next action. Link
  history in PRs, audits, job logs and handoffs instead of copying it. Line count
  alone is not the context budget; keep entries short rather than packing them
  into long lines. Reconcile adopted decisions and accepted progress into the
  plan of record.
- Keep a short friction log in the checkpoint or its linked Jocasta document:
  action attempted, observed failure/delay, impact and evidence. Record actual
  tool use, missing consumers, test flakes and review rounds, not speculation.
- Track merged milestones since the last audit and its per-repository source
  baseline/counting method. Run `/chaldea-audit` after five merged milestones,
  before starting a new roadmap step, or when the largest repository's source
  lines grow about 50% since the last audit, whichever comes first. Use
  `chaldea exec` for counts; these are audit triggers, never LOC budgets.
  Pause dependent roadmap work for Igor's adoption decisions, then record
  them and the new baseline in the report and checkpoint before continuing.
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
