---
name: review-delegation
description: Review cadence, fan-out reviews and delegation patterns for an interactive T3 session carrying out an agreed plan. Use when a milestone is ready for review, when writing a worker or reviewer brief for delegate_task, when deciding whether a review finding blocks, or when splitting work across child tasks.
---

# Reviews and delegation in T3 sessions

This expands the "Interactive work and delegation" section of the shared
instructions; where the two seem to differ, that section wins. Builders may launch their own
reviews, but every review must use T3 `delegate_task`.

## When to review

Review the final commit at each meaningful integration or release acceptance
batch required by the agreed plan. Preserve explicit acceptance boundaries.
Progress checkpoints and internal milestones within a related group do not each
create a PR or review pair. Group related work before review and CI as below:

- Prefer two independent fresh-context reviews, Sol 6.1 high and Opus 5.5 medium,
  using both providers whenever quota allows. The main reviewer uses the provider
  that did not write the change. Route the independent peer on its own provider.
- When quota is tight, two different models on the same provider are allowed,
  for example Sol and Astra, under the quota exception below. One independent
  review is acceptable when quota or availability prevents the desired pair.
- For consequential design or disputed findings, use the adopted critical anchors,
  Opus 5.5 high and Astra medium, through explicit user overrides or the documented
  outage fallback. Fable remains an optional explicit alternative or a stronger
  available-provider peer. Astra/Fable are not mandatory normal reviewers.
  Current router critical-review defaults still use Fable until separate code changes.
- Add at most one optional Luna/Haiku lens, with a concrete risk and exactly one
  bounded target, such as data safety or credential handling. No default review swarm. Conserve
  Claude; avoid optional Claude fan-outs.

OpenCode models are not used for reviews. Reviews stay within the brief. Report
each reviewer's thread ID, model and verdict in the reply and as a PR comment.

## How to run a round

Before each delegation, call FATE through `chaldea_route` or
`chaldea route --role ROLE`. Pass the selected `providerInstanceId`, `model`
and `options` exactly as the T3 `delegate_task` target, including effort.
Each route returns one target plus alternatives/byProvider, not a review pair.
The orchestrator selects each reviewer separately, calls FATE for each delegation
and launches two fresh contexts. Current pins still apply; this guidance adds no
automatic pair selection or joint model/effort optimizer.
Use `builder` for main diff reviews, `critical-review` for consequential design
or disputed findings, `bulk-read` for readers and `general` for other work.
For the main other-provider review, pass the writer's driver as `authorProvider`,
`claudeAgent` or `codex`, or CLI `--author-provider`. Route the independent peer
without that author-provider exclusion, under the pair or quota rule. Honor
explicit user/model overrides. If MCP rejects newer configuration keys,
use the installed CLI with the same constraints, without restarting T3.

For a Codex author, normally run
`chaldea route --role builder --author-provider codex`. A Codex builder pin
may refuse because it cannot satisfy provider separation. If FATE cannot
recommend a target, record the refusal and use the approved main-review
fallback from the live `orchestrator_capabilities` catalog: Opus 5.5 medium
for Codex-authored work, Sol 6.1 high for Claude-authored work. Pass the
catalog's exact provider/model IDs and the matching medium/high effort option. This is an
other-provider fallback, not a quota waiver. Do not retry a pin indefinitely.
Reject a same-provider target unless the quota exception qualifies. Compare
underlying provider drivers in the live catalog before launching, even if FATE
returned a target despite authorProvider. Such a recommendation is unusable
for the requested cross-provider review; record it and use the fallback.
Keep Claude use to the preferred pair and required main review. If the other-provider
fallback cannot run, record the evidence and apply the quota or single-review rule.
For other outage roles, use the `chaldea` skill's documented fallback.
Maximum effort is high; only Luna/Haiku may use xhigh.
These are ceilings, not defaults. Choose only available live-catalog models/options;
Haiku needs an available catalog target. Never use max, ultra, ultrathink or ultracode.

Start every review round, including re-reviews, as a fresh
`delegate_task` that carries the brief, the prior findings and the responses to
them; do not continue a review through `t3_thread_send` on a child thread. Give
each round its own `clientRequestId`. Launch the independent pair and any justified
bounded lens together; a finished child wakes the parent, so never poll.

## Quota exception

Use both providers whenever quota allows. When quota is tight, two independent
reviews on the same provider with different models are allowed. Keep a fresh independent context
through a new T3 `delegate_task` for each reviewer. For
Sol-authored Codex work, Sol 6.1 high plus Astra medium is an available-provider
pair, not a cross-provider review.

Record fresh quota evidence supporting pressure or a stop at selection, the
exception reason and reviewer provider/model/effort. A stop and a reset more
than one hour away are not prerequisites. Unknown quota, routing preference,
a missing recommendation or a collector HTTP 429 alone grant no waiver.
Never invent a reset timestamp. If quota or availability prevents two reviews,
one independent review is acceptable; record why the pair could not run.

Call FATE before every delegation. Route the main other-provider review with
`authorProvider` first. If that strict filter has no candidate under evidenced
quota pressure, record the exception, then resolve an appropriate available
target and effort from `orchestrator_capabilities`. Do not weaken the router's
filter or change routing code. Report each reviewer's thread ID, model, verdict
and exact reviewed commit in the reply and PR comment; record exception evidence
and review details in the checkpoint too.
No spending, reset redemption or authentication changes are authorized.

The exact reviewed commit, clean-tree acceptance, citation/location blocking
rule and two-fix-round limit below still apply. Existing reviews on an available
other provider continue.

## Check necessity and complexity

Ask whether the change is needed as well as whether it is correct. Before accepting
a new process, account, state store or publication path, trace the existing producer
and consumer and compare a configuration, version-pin or enrollment change.
Cite the exact missing capability or constraint that rules out reuse. Separate
verified facts, assumptions and optional improvements; check the premise independently
rather than accepting the brief's proposed architecture as a requirement.
Keep useful improvements outside the requested outcome as notes. Evidence of needless
complexity uses the existing citation/location blocking rule. Use existing authorized
evidence and report gaps; this check adds no review round or approval step.
For a plan review, also weigh information gained per time and token, and whether a
bounded spike could settle a question before any deployment.

## Group related work before review and CI

Prefer one PR for related changes delivering one outcome when the combined diff is
reviewable and has compatible authorization, deployment and rollback requirements.
Keep independent releases, unrelated changes or materially different risks separate.
Use separate commits and disjoint workers within a PR; do not create a PR per worker.
Plan dependency and merge order before expensive CI, especially with strict base rules.
Integrate ready related changes before final review and push them as a batch; do not
hold a useful delivery for speculative additions. Preserve repository ownership and
linked PRs across repositories. Batching never waives exact-head review or required CI.

## What blocks

- A finding blocks only when it cites a requirement from the brief or plan, or
  shows concrete evidence of a defect, and names a location. Anything else is a
  note.
- Findings outside the plan's scope become follow-up notes, not blocking work.
- ACCEPT names the exact commit, reviewed on a clean tree. After an accepted
  review, the orchestrator may verify a small follow-up without another review
  only when it is low risk and preserves reviewed behavior, acceptance and
  authority. Under about 50 lines is a sizing guide, not a waiver for security,
  authority, acceptance or behavior changes. Such changes and larger follow-ups
  need review of the final commit. Required tests and CI still apply.
- At most two fix rounds per milestone. After that the lead decides or asks
  Igor.
- The author may dispute a finding with a reason. Disputes go to a
  critical-review model or to Igor, not to another round of the same reviewer.

## Preserve review notes

At review completion, the root/worker preserves notes and verdict links in the PR and
existing Jocasta checkpoint/backlog, with exact reviewed heads, task/thread IDs, models,
citations/locations and source links. Publish native Akasha review notes/verdicts only
through a known authorized producer/path and retain its committed receipt. Schema support
alone does not prove delivery. If that path is unavailable, retain PR/Jocasta references
and report the collection gap. Never add grants silently or treat generic `feed_post`
as `review_note`. This guidance does not implement a collection pipeline.

## Delegating work

- Workers get no conversation history. Write a minimal self-contained brief:
  objective, repository path, branch and base, allowed files, the agreed interface,
  accepted decisions and exact evidence references the task needs, constraints,
  acceptance checks and what to report. Leave out the transcript and the global
  roadmap; do not prepend executor skills or require a full plan or checkpoint
  fetch for ordinary workers. The worker loads only its task's skills and relevant
  references. The parent owns integration and checkpoint unless the brief explicitly
  assigns a bounded sub-executor role as described below.
  Include only facts that can change this worker's action or verdict. Link exact
  evidence and relevant sections instead of copying terminal lanes, full skill
  bodies, tool catalogs or prior failure diaries. Keep authority, interfaces,
  safety constraints and unresolved review findings explicit; brevity never
  removes them. Use normal spacing and readable sentences.
- Ask for concise results: verdict, exact head and tree state, actual check
  outcomes with job IDs, remaining gaps and artifact links. No diary, raw logs or
  tool catalog; raw logs stay retrievable on request.
- Use `isolation: "worktree"` for code changes in a registered T3 project. A
  worktree starts from the parent's local commit; uncommitted edits are not
  copied.
- Split independent parts into parallel children only when their files do not
  overlap.
- Keep fix rounds focused, while retaining the original brief, prior findings,
  responses and unresolved objections in each new `delegate_task` prompt.
- Report implemented, reviewed, merged, deployed and verified as separate
  states. A passing task is not an accepted review, and a merge is not a
  deployment.

## Bounded sub-executor briefs

A related milestone group may explicitly own local orchestration under
sub-roadmap-executor. Use that skill's brief, with the minimal relevant plan excerpt,
exact evidence links, separate branch/worktree, local checkpoint, acceptance, budget
and stop conditions. Assign integration, merge and deployment rights explicitly or
reserve them to the root. The sub-executor advances routine milestones without parent
approval. The root retains global authority, interfaces, checkpoint and cross-group
integration; escalations to Igor go through the root. Ordinary worker briefs remain
narrow and do not inherit this role.

Allow nested builders/reviewers only when the live runtime supports them. Otherwise
the sub-executor does permitted implementation itself and sends exact review or
worker briefs to the root for dispatch, continuing independent ready work meanwhile.
Do not create further sub-executor layers by default. Propagate root cancellation
through all descendants, reconcile in-flight operations and report pending cleanup.
Review routing and exact-source gates apply at every supported delegation level.

## Review brief template

```text
Review <repository> at commit <sha> on branch <branch> (base <base-sha>).
Role: <main reviewer | fan-out reviewer for TARGET AREA only>.
Brief: <plan reference and the milestone's acceptance criteria>.
Scope: <files or diff range>. Out of scope: <what to leave alone>.
Necessity: <existing path and why configuration/pin/enrollment reuse is insufficient;
  n/a when no new process, account, state store or publication path is proposed>.
Distinguish verified constraints from assumptions and optional improvements.
Check two axes separately: repository documented standards and originating issue/spec.
Sources: <standards files/rules>; <issue/spec reference, or unavailable>.
Cite each applicable rule/requirement; do not let one axis mask the other.
Prior findings and responses: <list, or "none, first round">.
Check that the tree is clean at that commit. Do not edit files.
Return the verdict format below and nothing else.
```

## Verdict format

```text
VERDICT: ACCEPT | CHANGES_REQUESTED
COMMIT: <sha reviewed>
FINDINGS:
- severity: blocking | note
  citation: <requirement in the brief or plan, or the defect evidence>
  location: <path:line or symbol>
  finding: <what is wrong and why it matters>
  suggestion: <optional>
```

CHANGES_REQUESTED needs at least one blocking finding. A blocking finding
without a citation or location is treated as a note.
