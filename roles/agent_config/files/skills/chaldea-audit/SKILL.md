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
  milestones since the last one, when the largest repository's source lines grow
  about 50% since its baseline, or before a material unplanned change of direction
  or trust boundary. Routine roadmap steps do not each require a comprehensive
  audit. Follow adopted audit nodes and any proportionate cadence in the plan,
  retaining these fallbacks for unplanned drift. One audit covers coincident triggers.
- The checkpoint keeps merged milestones since the last comprehensive audit, its
  baseline and counting method, and due status. Never silently drop an
  unaddressed due audit. Counts use `chaldea exec`; they are triggers, never
  LOC budgets.
- Reuse completed spike, source, review, CI and deployment evidence by reference;
  read raw artifacts only for an unresolved finding. Rerun only changed or
  uncertain meaningful checks; no default full suite, repeated count job or
  review-pair ritual.

## Frame the audit

- Resolve the active plan, checkpoint and previous audit from the assignment and
  its exact references. Read their operative sections and relevant implementation
  briefs from Jocasta. Honor supplied scope; do not substitute a historical or
  stopped project's plan. Report missing references and continue evidence work
  that does not depend on them.
- Keep a routine consistency check inline using available source and evidence.
  It does not create a compulsory delegation or comprehensive audit.
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

- For a comprehensive audit, after the lenses finish, delegate one synthesis
  using `review-delegation`'s consequential-review selection and provider rules.
  Call FATE with `critical-review` before delegation, compare underlying drivers
  in the live catalog and prefer the other provider from most lenses. Apply its
  documented fallback and "Quota exception" with evidence when needed; no fixed
  Fable requirement overrides those rules. An inline decision check may synthesize
  its own bounded evidence without another agent.
- Give it all lens evidence and pinned context. It checks disputed evidence,
  merges duplicates and writes a ranked report to
  `tooling/handoffs/chaldea-audit-<date>.md` in Jocasta. Include scope/commits,
  reviewer thread IDs/models, numbers and delta against the previous audit,
  findings in audit-lens format, unknowns and proposed dispositions.
  Keep it to decisions, material findings and evidence links, not a diary.
  Fetch an existing same-date report in full and use WebMCP `if_revision`;
  create only if absent. Preserve earlier audit evidence and decisions.
- The orchestrator judges each recommendation and adopts reasonable, evidence-backed
  improvements within the agreed outcome, scope, authority and cost without asking
  Igor again. Reject or defer unsupported or unnecessary suggestions. Record the
  disposition and reason; an audit finding is evidence, not an instruction.
- Ask Igor only for a significant change of direction or a real unresolved choice:
  changed goals or acceptance, material scope/cost or architectural tradeoffs, or
  actions beyond existing authority. Existing deployment, credential and security
  boundaries still apply; routine adoption grants no additional permissions.
- Use roadmap-executor to identify the latest safe decision point and continue
  authorized work that does not depend on the answer. Ask in the conversation;
  use the Chaldea decision inbox only for material direction questions needing
  durable tracking or when Igor requests it. No answer only defers dependent work.
- Record orchestrator dispositions and any Igor decisions in the report, checkpoint
  and plan with full fetch/reconcile/WebMCP `if_revision`. Close a completed audit and
  update its reference and due status without waiting on unrelated proposals; only
  a comprehensive audit resets the comparable baseline and milestone counter.
  Unresolved blocking findings still gate the affected work.
- Keep the audit read-only. Carry out adopted improvements as separate execution
  work under existing authority, with the normal review, checks and release gates.
