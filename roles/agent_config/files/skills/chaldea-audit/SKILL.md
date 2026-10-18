---
name: chaldea-audit
description: >-
  Run /chaldea-audit [scope] for a read-only audit of Chaldea roadmap alignment,
  architecture, consistency, security, size, test health and session friction.
---

# Chaldea audit

Use for a requested audit or a roadmap-executor audit checkpoint, not ordinary
session work. The audit changes no source, PRs, services or hosts; its only writes
are scratch evidence and the Jocasta report and decision/checkpoint records.

## Frame the audit

- Read the current plan of record
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
scratch path and output destination. Cover these lenses (combine for small scopes):

1. Scope and roadmap alignment: plan order, measured need, unused capabilities,
   budgets versus actuals, and Igor decisions missing from the plan.
2. Logic duplication and ownership: repeated mechanisms, unjustified layers,
   code in configuration repositories, and the smallest consolidation.
3. Cross-component consistency: protocols, configuration, paths, pins, defaults,
   logging, errors and documentation versus implementation.
4. Security-boundary coherence: issuer, verifier and consumer contracts, trust,
   revocation, isolation, credentials and rollout prerequisites.
5. Size, test health, friction and reboot rules: source/tests/docs by component
   (vendor/generated separate), test ratios, PR/fix rounds, flakes, real use,
   interactive latency/polling, retention and any-host-down recovery.

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
  Fetch an existing same-date report in full and use `--if-revision N`;
  create only if absent. Preserve earlier audit evidence and decisions.
- The orchestrator judges the report, states which recommendations it supports
  and why, and asks Igor which to adopt. Use the chaldea skill's decision
  workflow for native input; unanswered recommendations remain pending.
- Record Igor's answers (adopt/reject/defer and reason) in the report and the
  checkpoint, using full fetch/reconcile/`--if-revision`. Update the checkpoint's
  audit reference, comparable source baseline and milestone counter. Decisions
  missing from the plan are named for reconciliation, not silently invented.
- Stop at the report and decisions. Implementation requires adopted scope;
  an audit recommendation itself grants no authority to change anything.
