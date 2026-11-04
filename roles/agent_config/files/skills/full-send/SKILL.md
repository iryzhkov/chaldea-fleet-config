---
name: full-send
description: Finish a requested task autonomously through verification, PR review and merge when the user explicitly says "full send". For non-code work, finish and verify the requested operational outcome.
---

# Full send

Use only when the user explicitly applies "full send" to a task. Mentioning or
researching this skill is not an invocation. The task's current restrictions,
higher-priority instructions, access controls and Stop/cancel still apply.
A later cancellation ends the assignment and its children, including after a wake.

"Full send" authorizes completing the requested change, publishing its task branch
and PR, fixing in-scope CI/review findings and merging through normal protection
when the gate below passes. Carry existing deployment authority through to the
requested installed and verified outcome. Do not infer authority for unrelated
production changes, destructive data loss, new cost or access/security changes.
Existing explicit source-only, no-deploy or no-merge restrictions remain binding.
Resolve genuinely conflicting requested outcomes before the dependent action.

## Execute to the outcome

1. Inspect current work, instructions and relevant OV knowledge. Preserve unrelated
   edits. Use agent-workflow for proportional planning and selective learning.
   Load its interactive runtime reference and review-delegation before delegation,
   review or orchestration. Use roadmap skills only for an actual roadmap.
2. Implement the smallest sufficient change. Diagnose routine failures and make
   ordinary implementation choices without asking the user to direct each step.
   Keep source operations in Huyang and executable checks in Chaldea.
3. Verify the requested behavior on the exact source. Use meaningful reproductions
   and required checks. Missing evidence is a limitation, never a passing check.
   Follow the runtime's available browser and tool rules; this skill overrides none.
4. Obtain independent acceptance under review-delegation's current routing, pair,
   quota, evidence and fix-round rules. Do not add a second competing review loop.
5. File or update a concise PR explaining the problem, result and verification.
   Link it to the current T3 thread immediately. Preserve contributor credit.
6. Handle existing CI and review findings. While waiting for actual dependencies,
   use native child completion or watch_pull_request and end the turn as required.
   A wait retains ownership; it does not mark the task complete. Do not poll, add
   background watchers or promise a wake the runtime cannot provide.
7. Recheck the gate, merge using the repository's normal method, then finish any
   authorized installation and live verification. Record useful OV learning
   selectively. Report the PR, outcome, proof and remaining limitations.

For a non-code task, follow the same scope, evidence and continuation rules.
A PR is needed only when the requested outcome changes versioned source.

## Merge gate and stop boundaries

On the live final head, require relevant proof, all required checks, required
independent acceptance, and no unresolved human change request or blocking finding.
Fetch the base and confirm the PR is current and mergeable. Recheck after any
meaningful fix or conflict resolution. Never bypass protection or use --admin.
A failed or unavailable reviewer is not approval. Budget exhaustion is not approval.

If blocked, continue useful independent work and retain the exact dependency,
owner, source revision, recovery action and evidence in the existing checkpoint.
Ask only for material unresolved direction, missing access or new authority.
Before handoff or a question, unwatch any PR owned by this thread. Do not declare
completion before merge and any requested activation are observed.
