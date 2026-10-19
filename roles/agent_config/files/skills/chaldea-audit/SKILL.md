---
name: chaldea-audit
description: >-
  Run /chaldea-audit [scope] for a read-only Chaldea decision check at a planned
  audit node, or a comprehensive audit of roadmap alignment, architecture,
  consistency, security, size, test health and session friction.
---

# Chaldea audit

Use for a requested audit, a due comprehensive audit or a planned audit node, not
ordinary session work. The audit changes no source, PRs, services or hosts; its
only writes are scratch evidence and the Jocasta report and decision/checkpoint
records. Code fixes happen separately under adopted scope.

## Size the audit to the decision

- A decision check answers one planned audit node or milestone question: its
  purpose, scope, the evidence it reuses and the decision it can change. Run it
  inline or with one bounded lens. It does not satisfy a due comprehensive audit
  or reset its counter, and its report says so.
- A comprehensive audit covers the lenses below. It is due after five merged
  milestones since the last one, before a new roadmap step, or when the largest
  repository's source lines grow about 50% since its baseline, whichever comes
  first. An adopted plan may set a proportionate cadence instead, keeping a
  fallback for unplanned drift. One audit covers coincident triggers.
- The checkpoint keeps merged milestones since the last comprehensive audit, its
  baseline and counting method, and due status. Never silently drop an
  unaddressed due audit. Counts use `chaldea exec`; they are triggers, never
  LOC budgets.
- Reuse completed spike, source, review, CI and deployment evidence by reference;
  read raw artifacts only for an unresolved finding. Rerun only changed or
  uncertain meaningful checks; no default full suite, repeated count job or
  review-pair ritual.

## Frame the audit

- Read the operative sections of the current plan of record
  `tooling/plans/chaldea-rebuild-plan-2026-10-16.md`, the execution checkpoint
  `tooling/handoffs/chaldea-execution-checkpoint.md`, the previous audit and
  relevant implementation briefs from Jocasta. Honor a supplied scope.
- Pin exact Jocasta revisions and repository commits/PR heads in the briefs.
  Use the previous audit's numbers and counting method as the baseline; report
  missing or incomparable measurements explicitly, never invent a delta.
- Give each reviewer a separate fresh-clone path under
  `~/.cache/chaldea-scratch/audit-<date>/<lens>/` and set TMPDIR there.
  No `/tmp`. Read `~/.config/agents/jocasta.md` before document writes.
- Call `orchestrator_capabilities` for live provider/model IDs. Budget at most
  six delegated agents total: up to five lenses, then one synthesis. No nested
  delegation or additional review rounds. Default lenses to Codex Luna 6; use
  Claude only where the synthesis's different-provider rule requires it.

## Parallel lenses

Launch up to five read-only reviewers with T3 `delegate_task`. Each brief says
"Load audit-lens first" and supplies scope, pinned inputs, repository URLs/refs,
scratch path and output destination; lens workers load audit-lens and task
skills only, not roadmap-executor, roadmap-planner or full roadmap history.
Cover these lenses (combine for small scopes):

1. Scope and roadmap alignment: plan order, measured need, unused capabilities,
   budgets versus actuals, and Igor decisions missing from the plan.
2. Logic duplication and ownership: repeated mechanisms, unjustified layers,
   code in configuration repositories, and the smallest consolidation.
   Check whether existing configuration, pins or enrollment can meet the same
   requirement before accepting new processes, identities, state or publication paths.
3. Cross-component consistency: protocols, configuration, paths, pins, defaults,
   logging, errors and documentation versus implementation.
4. Security-boundary coherence: issuer, verifier and consumer contracts, trust,
   revocation, isolation, credentials and rollout prerequisites.
5. Size, test health, friction and reboot rules: source/tests/docs by component
   (vendor/generated separate), test ratios, PR/fix rounds, flakes, real use,
   interactive latency/polling, retention and any-host-down recovery.
   Separate queue/setup, test, review, CI, integration and deployment time using
   retained evidence; assess missed acceptance outcomes and PR batching/merge-order
   costs as well as code size. Include measured time, token and process waste:
   deployments used to discover format, duplicate qualification, context reloads,
   queue/setup overhead and speculative machinery, against the cheapest
   trustworthy evidence path. Propose sized remedies with coverage and risk tradeoffs.

Assign heavy measurement only to lens 5 (or one named combined lens): line
counts, test suites and bounded flake reruns use `chaldea exec` without `--host`.
Other parallel lenses use the previous audit's numbers or name evidence gaps;
the synthesis incorporates the measurement lens's new results. Follow the chaldea skill for scratch HOME,
snapshot limits and uncertain jobs. Completion notifications wake the lead;
never poll. Recorded decisions are checked for drift, not re-argued.

## Synthesize and decide

- After the lenses finish, delegate one synthesis to a critical reviewer on
  the other provider from most lenses: Fable 5.1 for a Codex majority, Astra
  for a Claude majority, at medium effort. This consequential audit synthesis
  uses the critical-review role, subject to `review-delegation`'s provider rule
  and "Quota exception".
- Give it all lens evidence and pinned context. It checks disputed evidence,
  merges duplicates and writes a ranked report to
  `tooling/handoffs/chaldea-audit-<date>.md` in Jocasta. Include scope/commits,
  reviewer thread IDs/models, numbers and delta against the previous audit,
  findings in audit-lens format, unknowns and recommendations awaiting Igor.
  Keep it to decisions, material findings and evidence links, not a diary.
  Fetch an existing same-date report in full and use `--if-revision N`;
  create only if absent. Preserve earlier audit evidence and decisions.
- The orchestrator judges the report, states which recommendations it supports
  and why, and asks Igor which to adopt. Use the chaldea skill's decision
  workflow for native input; unanswered recommendations remain pending.
- Record Igor's answers (adopt/reject/defer and reason) in the report and the
  checkpoint, using full fetch/reconcile/`--if-revision`. Update the checkpoint's
  audit reference and due status; only a comprehensive audit resets the comparable
  source baseline and milestone counter. Decisions
  missing from the plan are named for reconciliation, not silently invented.
- Stop at the report and decisions. Implementation requires adopted scope;
  an audit recommendation itself grants no authority to change anything.
