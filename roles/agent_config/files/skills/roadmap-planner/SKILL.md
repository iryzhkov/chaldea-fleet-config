---
name: roadmap-planner
description: >-
  Create or materially revise an uncertain multi-milestone roadmap as the primary
  agent: settle decisive unknowns with research or bounded spikes, and plan test
  and deployment strategy, parallel lanes and audit nodes before implementation.
  Not for delegated workers, executing an adopted plan (roadmap-executor) or
  routine changes with a known path.
---

# Plan an uncertain roadmap

## When to use

- You are the primary agent creating or materially revising a multi-milestone
  plan whose architecture, data format, feasibility or deployment path is
  uncertain, including when execution evidence invalidates the adopted plan.

## When not to use

- Delegated implementer, reviewer, reader, operator or spike work: follow the brief.
- Executing an adopted plan: roadmap-executor. Routine or trivial changes with a
  known path: do them directly.

A request to complete work authorizes planning and routine implementation decisions
within that outcome. Present a plan for adoption only when a material unresolved
direction or substantial new cost needs Igor's choice. Apply standing host/homelab
authority from the shared instructions; do not add a separate deployment gate.
Honor explicit task limits and continue independent work while a choice is pending.

## Start from the outcome and what exists

State the user-observable outcome. Trace the existing authorized implementation,
producer, consumer and deployment evidence, and compare configuration, version-pin
and enrollment changes before estimating new machinery. Name the exact unmet
requirement before adding a process, account, state store or publication path.
Label verified facts, estimates and unknowns.

## Settle decisive unknowns cheaply

List only unknowns that would change architecture, format, feasibility or cost.
For each, take the cheapest trustworthy evidence: existing evidence, then research
on the exact question, then a bounded spike when that would change the decision.
Known or already-qualified seams need neither.

A spike is a legitimate milestone with an exact question, bounded scope and effort,
runnable proof with a retained artifact, a success/failure decision and a stop
condition. Prefer real producer output through the actual validator, ingest path or
consumer in an isolated Chaldea job; it can exercise schema, auth, ingest,
reads and data budget. Its result updates, reorders or removes dependent work; a
failed spike is no reason to build the planned machinery unchanged.

## Shape milestones and lanes

Plan the smallest useful end-to-end slice first, then expand. Each milestone names
its outcome, prerequisite or unknown, acceptance evidence and the decision it
enables. UI can build against qualified representative data while the backend
lands, then get a live UX check. Dependencies follow real data and ownership facts,
not habitual serial phases.

Name the next ready lanes, blockers and critical path. Parallel candidates:
independent bounded research and spikes, disjoint source workers against an agreed
small interface, UI on qualified fixtures beside the backend, CI and independent
review on a frozen head where the repository allows, and disjoint host rollouts
only when shared security and state ownership permit. Serialize dependent
schema/producer/consumer activation, conflicting files or branches, shared operator
access, exact-head qualification and irreversible effects. Keep one root owner for
global priorities, shared interfaces, authority, the global checkpoint and cross-group
integration. Batch ready related changes before expensive CI. Do not parallelize
speculative work or fan out by default.

For a related milestone group that benefits from local orchestration, explicitly
assign sub-roadmap-executor. Define outcomes, prerequisites, owned files/interfaces,
separate branch/worktree, local checkpoint, acceptance checks, budget, stop conditions,
report destination and integration/merge/deploy rights. Give only the relevant plan
excerpt and evidence links. It advances routine milestones without parent approval;
direction and authority escalations go through the root. Plan cancellation propagation
and a fallback if nested builder/reviewer delegation is unsupported, with no further
sub-executor layer by default. Ordinary workers keep narrow briefs.

## Decide test and deployment strategy up front

Write it once for related milestones, proportionate to risk, before implementation.
Mark a concern that does not apply in a word.

- Proof: the cheapest meaningful evidence: existing results, selected unit or
  contract tests, real isolated integration, and a representative live canary only
  where live behavior matters. Give exact commands and fixtures when known and a
  discovery spike when not.
- Environment: realistic toolchain and data, and compatibility with independently
  sourced dependencies and consumers.
- Boundaries: group review, CI and release to avoid strict-base churn and repeated
  full suites; reuse accepted exact-source evidence.
- Deployment: authorized targets, canonical method and order; consumers become
  compatible before a richer producer ships.
- Rollback: a concrete failure closeout and owner, verified feasible before
  mutation; finite holds only where relevant.
- Acceptance: observable natural delivery, errors, freshness and user outcome,
  including live UX.

Isolated jobs prove contract and viability, not live permissions, scheduling or
natural delivery; production verification proves those. Never deploy to the full
fleet to discover shape or viability, and never guess artifact pins. Weigh queue,
setup, integration, review, CI, deployment time and tokens when choosing, and keep
measurements apart from estimates. The strategy is the plan; execution receipts
are separate evidence.

## Place audit nodes

Add a reassessment where a decision or accumulated execution warrants it: after a
spike validates or refutes a premise and before dependent cost; before a broad
rollout or irreversible boundary; after a coherent execution batch or material
integration; on changed architecture, trust or dependencies, or repeated
unexplained friction. State its purpose, scope, evidence, the decision it can change
and proportionate effort. chaldea-audit separates these checks from a comprehensive
audit and owns due status.

## Review and record

Roadmap reviews follow review-delegation. Challenge needless full deployments,
redundant checks or reviews, excess documentation or context, speculative
infrastructure and serial work that could safely run in parallel, against the
cheapest evidence path. Concrete waste or a missed requirement blocks under the
normal citation rule; this adds no review gate.

Record the plan in Jocasta compactly: outcome, decisions, milestones, strategy,
lanes and audit nodes, linking evidence instead of copying it. Retain existing
authority, including approved operator and multi-host scope. Define observable
completion and any budget/stop boundary; milestone transitions are not approval gates.
For external dependencies, name owner, ID/source, expected wake, next action and recovery
deadline/action. Native question deadlines do not guarantee a wake or permission.
There is no fixed
research, spike, review, CI and all-host sequence. For a significant direction
choice, name the latest safe decision point and useful independent work so execution
can continue while Igor is unavailable. Roadmap-executor carries out the adopted
plan and routine adjustments; do not turn every revision into an adoption gate.
