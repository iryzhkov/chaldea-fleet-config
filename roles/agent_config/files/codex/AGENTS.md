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
through the `ov-memory` MCP server. Search it before answering questions about past work,
infrastructure or decisions; write to it only when asked. Record the fact and why it is
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

Run builds, tests, linters and code generators through `chaldea exec --host agent-a -- ...`
using a Git-independent make target or selected command. Set `HUYANG_FRICTION=0` inside
the job for every `go test`, for example:
`chaldea exec --host agent-a -- env HUYANG_FRICTION=0 go test ./...`.
Huyang handles source reads and guarded edits; Chaldea supplies build/test execution.
The `chaldea` skill covers snapshots, scratch and job outcomes.

Chaldea jobs omit `.git`. Run Git-dependent selection/planning locally only when it does
no build or test, for example `TEST_AFFECTED_LIST=1 make test-affected BASE=<pinned>`.
Keep the approved pinned base; pass selected packages, flags and required checks to the
job, for example `chaldea exec --host agent-a -- env HUYANG_FRICTION=0 go test -race <pkgs>`.
Split selection from execution for Git-dependent targets such as `test-affected`,
`check-fast` and `check-review` before dispatch. Actual builds/tests run only in Chaldea;
local selection is not verification.

Return generated outputs with `--artifact PATH` under `.chaldea/artifacts/<job-id>/`.
Review artifacts against current source and import through guarded Huyang edits:
`edit_apply kind=copy_file` for a missing destination, or a revision-guarded edit/change
plan for an existing file. Never overwrite repository source with shell commands.

`change_plan` prepare keeps its sandbox format/parser/check/test gates and project-command
trust policy. Inspect the evidence and apply only the returned prepared revision; skipped
checks in an untrusted root are not passing checks.

A result is valid only for the revision it names. Fix a refusal for a stale revision,
conflict or incomplete evidence rather than bypassing it with an unguarded overwrite.

Tool mapping, the cheapest correct call for each need, and the evidence rules: the
`huyang` skill, or **~/.config/agents/huyang.md**.

## Finishing agent-tooling changes

When working on agent tooling (Huyang, shared AGENTS.md/CLAUDE.md files, skills or MCP
configuration), finish a validated change by running its checks, pushing the source and
confirming its GitHub CI. Fleet distribution is manual until the replacement configuration
management exists: report which hosts were updated and verified and which were not, rather
than declaring a change distributed. An explicit user instruction to keep work local takes
precedence.

## Interactive work and delegation

Work happens in interactive T3 sessions. Stay interactive while exploring, designing and
making decisions turn by turn. Once Igor has agreed a plan, write it to Jocasta and carry it
out in the session; do not ask again for routine work inside that agreement.
When carrying out an agreed roadmap, load the roadmap-executor skill first.

Before delegating, call `chaldea_route` or `chaldea route --role ROLE` with `builder`,
`critical-review`, `bulk-read` or `general`. Pass its `providerInstanceId`, `model` and
`options` as the T3 `delegate_task` target. For reviews, pass `authorProvider` as the
writer's driver, `claudeAgent` or `codex`, to require the other provider. If routing is
unavailable, use the model roles below and preserve that cross-provider review rule.

Delegate through T3's own tools rather than a separate scheduler:

- `delegate_task` runs child work on any provider and model that `orchestrator_capabilities`
  lists (Claude, Codex, OpenCode). Use `isolation: "worktree"` for code changes in a
  registered repository project. A finished child wakes the parent; do not poll.
- Use the `review-delegation` skill for independent reviews, review rounds and worker briefs.
- `t3_thread_launch` is for separate top-level threads when Igor asks for them,
  `schedule_task` for recurring work, and `watch_pull_request` for following CI.
- Native same-provider subagents are for quick bounded reading and searching.

Builders may launch their own reviews, using T3 `delegate_task` only. Review the final
commit with one main reviewer on the other provider, plus at most one narrow fan-out
for security- or data-sensitive work. Allow at most two fix rounds. Report every
reviewer's thread ID, model and verdict in the reply and a PR comment. After an accepted
review, the orchestrator verifies a change of under about 50 lines without another review.

T3 tools act only on the host's own T3 server. There is no agent-driven launch on another
host yet; ask Igor to start work there from the T3 app.

Model roles: Opus 5.5 or Sol 6.1 at high effort for planning and execution; Fable 5.1 or
Astra at medium effort for critical review, including plan review; Haiku 5.5 or Luna 6 at medium effort for bulk reading, or whatever `chaldea route` recommends. Sonnet is excluded. Never use max effort or above. Read a quick lookup in a known file
directly.

Ask first when the estimated cost is large, the work needs operator-level access, or it
changes more than one host.

## Chaldea and scratch

Use the `chaldea` skill for builds and heavy runs on job hosts, durable waits and the
decision inbox. Get your own thread ID from `orchestrator_capabilities.parentThreadId`.
Before asking Igor through native T3 user input, call
`chaldea_decision_prepare({threadId, requestId, dependentAction, defaultAction, deadline})`.
Use `chaldea_decision_track` for a known native request and `chaldea_decision_status`
to read its state. Providers without native input use `chaldea_decision_ask` and
`chaldea_decision_answer` with the answering thread's `answeringThreadId`.
Defaults only skip or defer the dependent action; they never grant approval.

Use `chaldea exec` for builds and test suites instead of running them on omarchy-pc,
Igor's gaming PC. `--host` is optional: without it, `~/.config/chaldea/exec-hosts`
tries agent-a, agent-b, omarchy-pc when its game gate allows, then laptop when awake.
It moves on only after a refusal or an unreachable host before the request was sent.
Hosts run several jobs concurrently: agent-a 3, omarchy-pc 2, agent-b 1 and laptop 1.

On a quota stop, the session needs to do nothing: T3 resumes at reset; when enabled,
Chaldea's provider switch continues the same thread on an equivalent model. Never tell
Igor to resume manually.

Keep scratch on disk under `~/.cache/<task>/`, set `TMPDIR` there and tell workers the
path. Do not use host `/tmp`: it is RAM tmpfs with a quota. Tests must never write
outside a scratch HOME; assert the HOME is the intended scratch directory before writing.
A test overwrote a real key on 2026-10-17.

## Shared working documents

Use Jocasta for shared plans, handoffs and research. Search with `jocasta search`, fetch
the full document before an update, and use `--if-revision N`. Read
**~/.config/agents/jocasta.md** before creating or changing documents.
<!-- fleet:end -->
