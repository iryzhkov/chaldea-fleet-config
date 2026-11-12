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
refusal. Search before answering past-work, infrastructure or decision questions.
Use OV proactively for useful durable facts, decisions and lessons, including user
corrections, without per-note approval. Record the fact, scope and why it is true;
store a pointer to a credential, never the secret. Keep active task state in Jocasta.

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

Use agent-workflow for nontrivial work with 3+ meaningful steps or architectural
choices. It owns proportional planning, selective OV learning, verification,
autonomous diagnosis and durable task tracking. Ordinary workers follow their briefs.

Before delegation, independent review or orchestration, load review-delegation and
agent-workflow's references/interactive-runtime.md. That reference owns the shared
T3 lifecycle, routing, cancellation, review evidence and continuation requirements.
Use roadmap-planner for uncertain roadmaps, roadmap-executor when executing an
adopted roadmap, and sub-roadmap-executor only for explicitly assigned milestone groups.

Continue authorized ready work to observable completion or a genuine stop boundary.
Stop/cancel overrides late wakes. Use native child/PR dependencies; do not poll or
substitute external wakes. Retain dependency ownership and recovery when blocked.
Keep detailed receipts in PRs or Jocasta and give concise, meaningful chat updates.

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

Use the `chaldea` skill for builds and heavy runs on job hosts. Chaldea waits and the
decision inbox are retired because official T3 refuses their registration; use native T3.
Get your own thread ID from `orchestrator_capabilities.parentThreadId`.
Ask ordinary clarifying questions directly in the current conversation. Optional
preferences do not block work; use a reasonable in-scope assumption when safe.
Ask material direction questions the same way, through the runtime's own question
mechanism. Runtime
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
