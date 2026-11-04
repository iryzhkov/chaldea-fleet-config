# Interactive runtime requirements

Read before delegation, independent review or orchestration. This is the shared
runtime reference routed from the global instructions. review-delegation owns
review procedure, chaldea owns compute and routing fallback, and roadmap-executor
owns the adopted-roadmap lifecycle. Preserve the following runtime constraints.

Use agent-workflow for nontrivial work with 3+ meaningful steps or architectural
choices. It owns proportional planning, delegation, OV learning, verification,
simplicity, autonomous diagnosis and Jocasta tracking. Delegates help preserve the
parent's context by handling focused research, analysis and separable implementation;
the parent retains decisions and integration. Use T3 delegates under current runtime
rules and review-delegation; keep quick lookups direct.
When an adopted roadmap moves from planning to execution, load roadmap-executor
before implementation, even in the same thread. For material reshaping, load
roadmap-planner, then return to roadmap-executor. Skill loading follows the current
phase, not merely the thread's starting role.

Work happens in interactive T3 sessions. Stay interactive while exploring, designing and
making decisions turn by turn. For requested work, record the plan in Jocasta when needed and execute
assigned milestones through observable completion, explicit stop, an agreed budget limit,
or a blocker with no useful authorized ready work left. Milestone or review completion,
context compaction and monitor registration do not end the assignment.
Retain existing authority across turns and handoffs. Adopt reasonable audit improvements
within that outcome, scope and authority, recording why. Ask only when a concrete next
action needs new authority or a material direction choice remains unresolved. Continue
independent authorized work until the dependent work reaches its safe boundary.
Keep the evolving objective, accepted decisions and integration in the parent. Delegate
substantial searches, log analysis, independent investigations and separable implementation
when their detail would crowd its context. Useful sequential delegation counts too.
Keep quick lookups and tightly coupled decisions direct; weigh launch and integration
overhead without automatic fan-out. Open-ended work can contain bounded children.
Use review-delegation for briefs, steering and evidence. Retain the current objective,
accepted decisions, active task IDs and next action; use Jocasta for durable continuation
or handoff. Short investigations need no roadmap or checkpoint ceremony.
When executing an adopted roadmap as root, load roadmap-executor first. Ordinary parent
delegation does not itself make a roadmap. An explicitly assigned bounded milestone group
uses sub-roadmap-executor and its local checkpoint; ordinary workers follow their narrow
briefs. The parent owns integration and authority within its assignment.
Yield only after useful independent ready work is exhausted. Retain dependency owner,
task/PR/wait ID, source revision, expected wake, next action, recovery deadline and action.
At authorized executor kickoff on an already active, unsnoozed thread, inspect prior
pin/lifecycle state through available native state or public projection. If verified
unpinned, use `t3_thread_organize` action `pin`; record prior pin, resulting `pinnedAt`,
ownership and cleanup owner in the existing checkpoint. Do not invent metadata absent
from `t3_thread_read`. Pin excludes automatic settlement; it is neither a keepalive
nor permission.
At completion/explicit stop remove only a still-matching executor-owned pin; preserve
user pins/changes and carry ownership on handoff. If state is unverifiable, retain the
gap/cleanup obligation rather than blind unpin. Never pin, unsettle or resume stopped,
settled, archived or snoozed work from a late wake.
Use Stop/cancel to cancel the assignment and children. Manual Settle only organizes
thread state; native child completion may reopen it. Stop/user cancellation still wins.
Use native `delegate_task` completion and `watch_pull_request` for actual dependencies.
PR checks/comments/conflicts can wake; merge ends the watch silently. After CI, handle
your own authorized merge and continue, or retain owner/recovery for an external merge.
On official T3 0.1.0, do not replace Stop-preserving executor dependencies with external
Chaldea time/thread wakes. Keep historical guarded payloads fail-closed, never strip or
replay them. Record any missing native wake, owner and next authorized recovery; do not
promise guaranteed continuation or add a fork, wrapper, store or daemon. No dummy child,
fake recurring schedule, duplicate monitor or polling loop. Explicit stop/cancellation
overrides late wakes; reconcile outcomes before continuing.

Batch routine child and CI notifications into meaningful milestone updates. Surface material
failures, blockers, needed decisions or changed plans promptly. A wake should advance or
reconcile work, not automatically send a "still waiting" reply. Answer requested status
promptly and keep long work visibly interactive; higher-priority runtime communication
rules apply. Keep chat to short verdicts and receipt links; detailed IDs, review history,
commands and receipts belong in PRs, checkpoints or linked artifacts. Distinguish waiting
from completion and implemented, reviewed, merged, installed and verified states.
Propagate direction changes to affected children; cancel superseded work, mark obsolete
results and reconcile in-flight mutations before replacement or retry. Stop/cancel wins.
Keep optional discoveries as separate follow-ups, not silent scope expansion or blockers.

Choose the smallest sufficient change for established requirements and current constraints.
Extra layers or optimization need a current unmet requirement, measured bottleneck or
specific evidenced failure risk. Keep validation proportional to the stated behavior and
blast radius; stop when required claims are established. Preserve required tests, CI, security
and data protection. Apply review-delegation's necessity rules during execution when support
or qualification work starts dominating the outcome.

Before each T3 `delegate_task`, call FATE through `chaldea_route` or
`chaldea route --role ROLE`. Use `builder` for implementation and main diff reviews,
`critical-review` for consequential design or disputed findings, `bulk-read` for readers
and `general` for other work. Pass the selected `providerInstanceId`, `model` and
`options` exactly as the delegate target, including effort. Honor explicit user overrides.
For the main other-provider review pass the writer's driver as `authorProvider`,
`claudeAgent` or `codex`, or CLI `--author-provider`. Compare underlying provider drivers
in the live catalog. Reject a same-provider target for that review unless the quota
exception qualifies. Route the independent peer under `review-delegation`'s pair rule.
A recommendation that violates the requested separation is unusable; apply the fallback below.

If a long-lived MCP rejects newer configuration keys, use the installed CLI before
declaring routing unavailable. No T3 restart is needed. If neither can recommend a
target, use the `chaldea` skill's documented outage fallback with live catalog IDs.
A Codex builder pin may refuse a Codex author's main review; use the approved
other-provider main-review fallback in `review-delegation`, not repeated pin retries.
Cross-provider review remains the default. Only its "Quota exception" permits a waiver.

Delegate through T3's own tools rather than a separate scheduler:

- `delegate_task` runs child work on any provider and model that `orchestrator_capabilities`
  lists (Claude, Codex, OpenCode). Use `isolation: "worktree"` for code changes in a
  registered repository project. A finished child wakes the parent; do not poll.
- Use the `review-delegation` skill for independent reviews, review rounds and worker briefs.
- `t3_thread_launch` is for separate top-level threads when Igor asks for them,
  `schedule_task` for recurring work, and `watch_pull_request` for following CI.
- Native same-provider subagents are for quick bounded reading and searching.

Builders may launch their own reviews, using fresh T3 `delegate_task` contexts only.
Review meaningful integration/release acceptance batches, preserving the plan's required
boundaries. Progress checkpoints and internal group milestones do not each require a PR or
review pair. Prefer two independent reviews of the final commit, Sol 6.1 high and Opus 5.5 medium,
with the main reviewer on the other provider whenever quota allows. When quota is tight,
two different models on the same provider are allowed with fresh quota evidence and an
honestly labeled exception. One independent review is acceptable when quota or availability
prevents the pair. Follow `review-delegation` for routing and evidence. Optional Luna/Haiku
lenses need a concrete risk and a bounded target; no default swarm. Allow at most two fix
rounds. Preserve every reviewer's exact task/thread IDs, model, verdict and reviewed commit
in a PR comment and any existing checkpoint, or a linked durable receipt. Use a short
verdict and receipt link in chat.
After an accepted review, the orchestrator may verify a small follow-up without another
review only when it is low risk and preserves reviewed behavior, acceptance and authority.
Under about 50 lines alone grants no waiver for security, authority, acceptance or behavior
changes. Required tests and CI still apply.

T3 tools act only on their host's T3 server. Do not infer cross-host launch from
local tools. If Igor explicitly requests a fresh caller on another authorized host,
the verified installed host-local `orchestration.launchThread` API can create that
caller over approved SSH. Verify its actual schema, environment/project and least
scopes, save exact IDs before dispatch, reconcile uncertainty without blind retry,
and revoke the temporary control. Create only the requested caller; this is not
blanket cross-host model/delegation authority. Do not add a generic remote bridge
or replay an obsolete `t3-run` payload. Without a verified seam, ask Igor to start
the thread in T3. Never resume a stopped or settled thread without authorization.

FATE selects targets within the adopted review pair and role rules; explicit user
model overrides still apply. Use the documented outage fallback when routing is unavailable. Sonnet is excluded; Haiku is
allowed when selected. Maximum effort is high; only Luna/Haiku may use xhigh.
These are ceilings, not defaults. Choose only available live-catalog models/options;
Haiku needs an available catalog target. Never use max, ultra, ultrathink or ultracode.
Conserve Claude for required main cross-provider reviews; avoid optional Claude fan-outs.
Read a quick lookup in a known file directly. Reuse guidance already read while
its version and applicability remain valid. Project tool output to needed fields
and read one channel when text and structured responses duplicate each other.
Reduce context by selecting relevant material, not by packing words together.

