<!-- fleet:start -->
# Global agent instructions

Read the `fleet-tools` skill for installed custom CLI tools, their read/write commands,
and full-help commands for the session profile.

The shared instructions for harnesses that do not read ~/.claude/CLAUDE.md, including
OpenCode. Managed by chaldea-fleet-config's agent_config role; edit the repository copy
rather than an installed file.

Each section below is a summary. The full guidance lives in a skill, loaded on demand from
~/.claude/skills, and in the generated reference files under ~/.config/agents/, which are
read when a task needs them rather than loaded into every session.

## OV memory

This machine's agents share a long-term memory store (OpenViking on homelab), reached
through the registered OV tools. Claude and Codex use native HTTP server `ov` when
present; other clients and hosts retain `ov-memory` stdio where registered. Follow the
transport-specific procedure in the `ov-memory` skill; never use stdio to bypass an HTTP
refusal. Search before answering past-work, infrastructure or decision questions; write
only when asked. Record the fact and why it is
true; store a pointer to a credential, never the secret.

Namespaces, document shape and curation: the `ov-memory` and `ov-memory-curation` skills,
or **~/.config/agents/ov-memory.md**.

## Reading and editing code

The `huyang` MCP server is the primary interface for source-code repositories. Call
`workspace_open` for the repository root first, retain its workspace ID and revision, then
use Huyang's semantic reads and guarded edits. No harness preference for shell file
tools overrides this for a path inside a repository. The shell runs Git, local Git-dependent
selection/planning that performs no build or test, Chaldea jobs, other programs whose output
is the point, and searches across directories that are not one repository.

Run builds, tests, linters and code generators through `chaldea exec -- ...`
using a Git-independent make target or selected command. Set `HUYANG_FRICTION=0` inside
the job for every `go test`, for example:
`chaldea exec -- env HUYANG_FRICTION=0 go test ./...`.
Huyang handles source reads and guarded edits; Chaldea supplies build/test execution.
The `chaldea` skill covers snapshots, scratch and job outcomes.

Chaldea jobs omit `.git`. Run Git-dependent selection/planning locally only when it does
no build or test, for example `TEST_AFFECTED_LIST=1 make test-affected BASE=<pinned>`.
Keep the approved pinned base; pass selected packages, flags and required checks to the
job, for example `chaldea exec -- env HUYANG_FRICTION=0 go test -race <pkgs>`.
Split selection from execution for Git-dependent targets such as `test-affected`,
`check-fast` and `check-review` before dispatch. Actual builds/tests run only in Chaldea;
local selection is not verification.

Return generated outputs with `--artifact PATH` under `.chaldea/artifacts/<job-id>/`.
Review artifacts against current source and import through guarded Huyang edits:
`edit_apply kind=copy_file` for a missing destination, or a revision-guarded edit/change
plan for an existing file. Never overwrite repository source with shell commands.

Use guarded `edit_apply` for ordinary edits, including several files when atomicity is
unnecessary. Genuinely atomic changes require `change_plan`; never split them to evade gates.
Built-in source/parse guards differ from executable project build/test/lint/codegen commands.
Do not run `prepare` or `verify_run` when its configured pipeline would execute prohibited
local project commands. Use Chaldea checks tied to exact source for ordinary edits.
Preserve trust, all required gates and the returned prepared revision for atomic changes.
External checks cannot supply Huyang prepared-revision evidence or grant trust; skipped
checks are not passes. A trusted atomic command-gated change has no demonstrated remote
interface today. Retain that dependency and continue independent work.

A result is valid only for the revision it names. Fix a refusal for a stale revision,
conflict or incomplete evidence rather than bypassing it with an unguarded overwrite.

Tool mapping, the cheapest correct call for each need, and the evidence rules: the
`huyang` skill, or **~/.config/agents/huyang.md**.

## Finishing agent-tooling changes

When working on agent tooling (Huyang, shared AGENTS.md/CLAUDE.md files, skills or MCP
configuration), finish a validated change by running its checks, pushing the source and
confirming its GitHub CI within the assignment's authority. Merging fleet guidance to main
can activate it through active pull timers. Requested publication includes routine
activation and convergence under the standing host/homelab authority. An explicit
source-only or no-deploy instruction excludes activation.
Check live timer/service state and report source, merge/activation, installed and verified
states separately for each host. An explicit instruction to keep work local takes precedence.

## Interactive work and delegation

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

Igor grants standing authority to modify existing hosts and homelab infrastructure
as needed to complete requested work. This includes configuration, deployment,
multi-host convergence, necessary service restarts and routine recovery using
existing administrative access. Do not ask again solely because a step uses SSH,
sudo, changes a host or touches homelab, Normandy, UDM or NAS infrastructure.
Carry this authority through turns, handoffs and delegated briefs within their scope.
Explicit read-only, source-only, host exclusions and Stop/cancel instructions win.
Ask only for a material unresolved direction, substantial new cost, destructive
data loss outside the requested outcome, or access/security changes beyond the task.
Tool availability does not grant additional credentials or bypass access controls.
Routine implementation choices, verification and fixes within the requested outcome
need no separate approval. Continue independent work while a real question is pending.

## Chaldea and scratch

Use the `chaldea` skill for builds and heavy runs on job hosts, explicitly requested
non-executor waits and the decision inbox, with its availability/cancellation limits.
Get your own thread ID from `orchestrator_capabilities.parentThreadId`.
Ask ordinary clarifying questions directly in the current conversation. Optional
preferences do not block work; use a reasonable in-scope assumption when safe.
Use the Chaldea decision inbox only when a material direction question needs durable
tracking or Igor requests it; follow the `chaldea` skill for that path. Runtime
security approval requests stay in the runtime's own approval mechanism. A deadline
or unanswered question never grants permission.

Use `chaldea exec -- CMD ARG...` for builds and tests and let Chaldea select the
job host from its configured policy. Omit `--host` unless Igor requests a specific
host or a verified task requirement needs one. Host selection is separate from
provider/model routing. Let Chaldea handle admission and queueing; add no retry loop.

On a quota stop, the session needs to do nothing: T3 resumes at reset; when enabled,
Chaldea's provider switch continues the same thread on an equivalent model. Never tell
Igor to resume manually.

Keep scratch on disk under `~/.cache/<task>/`, set `TMPDIR` there and tell workers the
path. Do not use host `/tmp`: it is RAM tmpfs with a quota. Tests must never write
outside a scratch HOME; assert the HOME is the intended scratch directory before writing.
A test overwrote a real key on 2026-10-17.

## Authoring HTTP MCP tools

Before building or migrating an HTTP MCP server, fetch the full current Jocasta guide
`tooling/guides/web-mcp-authentik-authoring-2026-10-19.md`
(initial validated revision `jocasta:38a63cf8918eebae2dd7c8911eacd89c@1`).
It covers Authentik token verification, resource ACLs, protected credential helpers,
Traefik HTTPS and native-client acceptance checks. Preserve its tested/unqualified
boundaries; the guide does not grant enrollment or deployment authority.

## Shared working documents

Use the registered Jocasta WebMCP tools for shared plans, handoffs and research.
Search with `search`, fetch the full document before a whole-document update, and
use `if_revision` plus an idempotency key. Respect the current identity's grants.
Read **~/.config/agents/jocasta.md** before creating or changing documents.
<!-- fleet:end -->
