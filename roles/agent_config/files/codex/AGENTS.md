<!-- fleet:start -->
# Global agent instructions

The shared instructions for the harnesses that do not read ~/.claude/CLAUDE.md. Generated
by `agents-instructions-gen` from omarchy-setup's config/bin/agents-instructions-gen; edit
it there and regenerate rather than editing an installed copy.

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
use Huyang's semantic reads and transactional edits. No harness preference for shell file
tools overrides this for a path inside a repository. The shell runs only Git, builds and
tests, other programs whose output is the point, and searches across directories that are
not one repository.

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

Delegate through T3's own tools rather than a separate scheduler:

- `delegate_task` runs child work on any provider and model that `orchestrator_capabilities`
  lists (Claude, Codex, OpenCode). Use `isolation: "worktree"` for code changes in a
  registered repository project. A finished child wakes the parent; do not poll.
- Independent review goes to a different provider from the one that wrote the change. Start
  each review round as a new `delegate_task` carrying the brief, prior findings and the
  responses to them. Only findings that cite a defect, regression, safety problem or unmet
  requirement block; other notes become follow-ups.
- `t3_thread_launch` is for separate top-level threads when Igor asks for them,
  `schedule_task` for recurring work, and `watch_pull_request` for following CI.
- Native same-provider subagents are for quick bounded reading and searching.

T3 tools act only on the host's own T3 server. There is no agent-driven launch on another
host yet; ask Igor to start work there from the T3 app.

Model roles: Opus 5.5 or Sol 6.1 at high effort for planning and execution; Fable 5.1 or
Astra at medium effort for critical review, including plan review; Sonnet 5.5, Haiku 5.5 or
Luna 6 for bulk reading. Never use max effort or above. Read a quick lookup in a known file
directly.

Ask first when the estimated cost is large, the work needs operator-level access, or it
changes more than one host.

## Shared working documents

Use Jocasta for shared plans, handoffs and research. Search with `jocasta search`, fetch
the full document before an update, and use `--if-revision N`. Read
**~/.config/agents/jocasta.md** before creating or changing documents.
<!-- fleet:end -->
