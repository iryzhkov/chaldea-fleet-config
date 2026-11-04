---
name: agent-workflow
description: >-
  Shared workflow for nontrivial agent work: proportional planning, focused
  delegation, OV learning, verification and Jocasta tracking. Use for parent
  tasks with 3+ meaningful steps or architectural choices; roadmap skills own
  their distinct planning and execution roles. Ordinary workers follow briefs.
---

# Shared agent workflow

Use this policy across planning and execution. Load only the specialist skills
needed for the current action; a phase change in the same thread can require a
new skill. This policy adds no approval gate and does not expand task authority.

## Plan proportionately and switch roles

For work with 3+ meaningful steps or architectural decisions, write a short
checkable plan before implementation. Include the outcome, constraints and how
to verify it. A short task can use the current conversation's plan facility.
Use Jocasta when work needs durable continuation, milestones or coordination.
Do not create a roadmap merely to satisfy a step count.

Use roadmap-planner to design or materially reshape an uncertain multi-milestone
roadmap. Once the plan is adopted within existing authority and execution starts,
load roadmap-executor before implementation, even in the same thread. Planning
does not load execution instructions automatically. The root owns the global
checkpoint; an explicitly assigned milestone-group owner uses sub-roadmap-executor.
Ordinary workers follow their briefs, without inheriting orchestrator ceremony.

When evidence invalidates the plan, stop dependent work and revise it. Load
roadmap-planner for material reshaping, then return to roadmap-executor for
execution. Continue useful independent work within authority. Routine plan
adjustments need no renewed adoption or user approval.

## Delegate focused work

Delegates are useful for substantial research, log analysis, independent review
and separable implementation. They keep detailed working material out of the
parent context and can explore independent questions in parallel or sequentially.
The parent retains the objective, accepted decisions and integration.

Give each delegate one bounded outcome, relevant evidence, ownership, acceptance
and stop conditions. Use T3 delegate_task for durable/background work, separate
checkouts, cross-provider work and reviews, under the runtime's supported rules.
Native subagents suit quick bounded same-provider reading when supported.
Keep quick lookups and tightly coupled decisions direct; weigh launch and
integration cost. Do not fan out automatically or let agents edit conflicting
files concurrently. review-delegation owns briefs, routing and review policy.
Before delegation, independent review or orchestration, read
[interactive runtime requirements](references/interactive-runtime.md).

## Learn through OV

Use OV proactively as the agents' durable knowledge store. Search relevant
knowledge before relying on assumptions about past decisions or systems.
After a user correction, capture a reusable lesson when it changes future work:
what was wrong, the correct behavior, its scope and why it is true. Agents may
also retain useful verified discoveries and decisions without per-note approval.

Search for an existing note first and reconcile rather than duplicate it.
Do not turn a one-off instruction into a universal rule. Keep secrets, raw
transcripts and temporary task state out. Link source evidence rather than
mirror repositories or Jocasta documents. ov-memory owns transport, safe updates
and verification. Memory records knowledge; it does not override instructions,
grant authority or expand tool access.

Before completion, check whether this task produced a reusable correction,
verified discovery or decision. If useful, search for an existing note, reconcile
or create it under ov-memory's safe-write procedure and read back the content.
Otherwise skip the write. Do not create a note merely to satisfy a completion
ritual or count. Record an unavailable write as a gap, never as saved knowledge.
A content readback does not establish revision-bound search indexing.

## Verify before completion

Define meaningful proof in the plan and check the actual claimed outcome.
Use Huyang for source reads and guarded edits, Chaldea for executable checks,
and review-delegation for required independent acceptance. Compare behavior
with the base when relevant. Retain exact-source receipts and report limitations.
Source changes, passing tests, merge, installation and live verification are
different states; claim only those supported by evidence.

## Prefer the simplest sound solution

For substantial changes, reconsider whether the solution fits the existing
system and whether a simpler design would remove complexity. Rework an awkward
fix when that improves the current outcome. Keep obvious fixes small; elegance
does not justify extra layers, speculative optimization or expanded scope.
Use review-delegation's necessity rules in the existing review.

## Diagnose and fix autonomously

Use logs, errors, source and failing tests to find the cause and resolve bugs
within the requested outcome. Load diagnosing-bugs for difficult diagnosis.
Do not require the user to direct routine investigation or CI fixes. Distinguish
a hypothesis from a confirmed cause; reconcile uncertain operations before retry.
Ask only for material unresolved direction, missing access or new authority.

## Track progress where it belongs

Jocasta holds durable plans, current checkpoints and linked evidence. Update
checkable progress and the next action at meaningful state changes; keep each
fact in its owning document. OV holds reusable knowledge across tasks.
Do not create parallel tasks/todo.md or tasks/lessons.md stores by default.
Keep the user informed of findings and changed plans. Continue authorized ready
work to observable completion or a genuine stop boundary. Existing cancellation,
dependency ownership, review and deployment safeguards remain in force.
