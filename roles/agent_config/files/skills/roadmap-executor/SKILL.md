---
name: roadmap-executor
description: >-
  Execute an agreed roadmap or plan of record as the orchestrator. Load first
  when carrying out roadmap work, resuming orchestration, or taking over an
  execution handoff; keep milestones, decisions and the next handoff resumable.
---

# Execute the agreed roadmap

This is a tool for agreed plan execution, not a startup checklist for ordinary
sessions. Continue routine work inside Igor's agreement without asking again.

## Resume from durable state

- First fetch the full plan of record and execution checkpoint from Jocasta.
  For Chaldea these are `tooling/plans/chaldea-rebuild-plan-2026-10-16.md` and
  `tooling/handoffs/chaldea-execution-checkpoint.md`. Read relevant briefs,
  recorded decisions and the latest audit; use current revisions, not old
  transcript summaries. A supplied handoff points to these, not replaces them.
- Keep plan order, measured-friction reasons, simplicity guardrails and budgets.
  Re-scope overruns with Igor; do not add capabilities without a measured need
  or his decision. Recorded decisions are binding, not review debate topics.
- Read `~/.config/agents/jocasta.md` before writes. Fetch in full, reconcile
  and update with `--if-revision N`; never overwrite a concurrent update.

## Delegate and follow work

- Before each T3 `delegate_task`, call FATE through `chaldea_route` or
  `chaldea route --role ROLE`. Pass the selected `providerInstanceId`, `model`
  and `options` exactly as the delegate target, including effort.
  Use `builder` for implementation and main diff reviews, `critical-review` for
  consequential design or disputed findings, `bulk-read` for readers and `general`
  for other work. Main other-provider reviews pass the writer's driver as
  `authorProvider`, `claudeAgent` or `codex`, or CLI `--author-provider`. Route the
  independent peer under `review-delegation`'s pair rule. Honor
  explicit user/model overrides. If MCP rejects newer configuration keys, use the
  installed CLI without restarting T3. If neither can recommend a target, use the
  `chaldea` skill's documented outage fallback and live catalog IDs. For main reviews,
  a Codex builder pin refusal uses `review-delegation`'s approved other-provider
  main-review fallback. Apply its provider rule and "Quota exception", including
  its PR comment and checkpoint evidence. Reject a same-provider target unless
  that quota exception qualifies; compare underlying provider drivers in the live
  catalog. Never use max effort or above.
- Load review-delegation for self-contained worker briefs, worktree isolation
  and review rules. Prefer independent Sol 6.1 high and Opus 5.5 high reviews with
  both providers whenever quota allows. Its "Quota exception" allows two different
  models on one provider when quota is tight, with fresh evidence and honest labeling;
  one independent review is acceptable if quota or availability prevents the pair. Builders may run their own compliant T3 reviews; reuse
  their final-commit acceptance rather than repeating it. Do not restate or
  enlarge that skill's review process.
- Give workers exact repositories/refs, allowed files, acceptance commands,
  decisions, scratch paths and deployment boundaries. Require Huyang for
  repository reads/edits and `chaldea exec` for builds/tests/heavy runs.
  Load chaldea for snapshots, artifacts, scratch HOME and uncertain outcomes.
- Children wake the parent on completion. Use `watch_pull_request` for CI and
  review events and Chaldea waits for external time/thread dependencies.
  Several waits per thread are allowed; save their IDs and retry keys.
  Register then yield; never poll, sleep-loop or create duplicate watchers.
  Quota recovery resumes automatically; do not ask Igor to resume manually.

## Merge and converge within authorization

- Merge only the exact accepted head on a clean tree with required CI green
  and prior findings resolved under review-delegation. Link each PR in T3.
  Report implemented, reviewed, merged, deployed and verified separately.
- Ask Igor before changes to multiple hosts, credentials, homelab or Normandy
  deployments, or UDM/NAS work, unless that exact scope is already authorized.
  Source implementation is not deployment authority. Never expose secrets.
- Load fleet-rollout for authorized deployments: pinned host-side ansible-pull,
  check, real, second real `changed=0`, and before/after unit/timer snapshots.
  It owns the converge procedure; report verification evidence per host.
- Background long converges in delegated threads, using their completion wake
  or one Chaldea thread wait for a non-child thread. Preserve command, target,
  log and outcome; reconcile a disconnect or reboot before any retry.
- Any host may reboot without breaking the rest. Do not reboot as a routine
  recovery action. Restart T3 only with `chaldea t3 restart` once that command
  exists, within explicit authorization; until then defer and ask Igor.
  Do not substitute a raw service restart.

## Keep the next milestone resumable

- After every milestone, update the checkpoint: current lanes, exact commits/
  PRs, review thread IDs/models/verdicts, CI, deployment/verification by host,
  open decisions/risks and next action. Keep it compact (aim under 80 lines,
  about five per lane); history belongs in linked PRs, audits and handoffs.
  Reconcile adopted decisions and accepted progress into the plan of record.
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
- End the execution session with a Jocasta handoff whose literal first line is
  "Load the roadmap-executor skill first." Include exact plan/checkpoint/audit
  references, active task/thread/run/wait IDs, repository branches and commits,
  PRs/CI/reviews, permissions, blockers and the next concrete action.

## Focused handoff / kickoff template

Fill from verified evidence, remove unused clauses and unresolved placeholders,
and link detailed logs. Preparing a prompt does not authorize its execution.
Keep the first milestone end to end; investigate an uncertain seam before a
broad build. Preserve successful checks and diagnose repeated failures rather
than retrying the same repair or weakening verification.

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
