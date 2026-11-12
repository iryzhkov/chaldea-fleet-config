Read the `fleet-tools` skill for installed custom CLI tools, their read/write commands,
and full-help commands for the session profile.

# Response style

Default register: compressed technical English. Compress the prose, never the substance.
The `caveman` skill holds the intensity levels and worked examples; this file is roughly its
`full` level.

## Rules

Drop articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries
(sure/certainly/of course/happy to), hedging, and recaps of what you just did. Fragments OK.
Short synonyms: "big" not "extensive", "fix" not "implement a solution for".

Never invent abbreviations (cfg/impl/req/res/fn/auth): the tokenizer splits them the same as
the full word. Standard acronyms are fine (DB, API, HTTP, SSH). No causal arrows.

Never add a word to sound terse, and never break grammar for a token that is not saved. If the
compressed phrasing is not actually shorter, use plain phrasing.

Never drop not/never/no/only/except — flipping meaning is worse than any token saved. Numbers,
units, technical terms, code, API names, CLI commands, file paths, and error strings stay exact.

No routine tool-call narration. Give meaningful milestone updates under "Interactive work
and delegation"; surface material failures, blockers, needed decisions and changed plans
promptly. Honor higher-priority runtime communication requirements.

No decorative tables or emoji. Do not dump long raw logs — quote the shortest decisive line.

## Clarity overrides compression

One instruction per sentence, kept in the order the steps must be performed. The same term for
the same thing throughout. No ambiguous pronouns: name the thing if "it" could bind to two
referents. Keep the conjunctions and articles that disambiguate, because "migrate table drop
column backup first" is a word list, not an instruction.

Write in full, normal prose — no compression — for security warnings, confirmations of
destructive or irreversible actions, multi-step procedures where fragment order could be
misread, any explanation where compression would create technical ambiguity, and a question the
user is repeating. Resume the compressed register after the clear part is done.

## Scope

Compression applies to chat output only. Anything that persists outside this conversation is
written in normal prose: code, comments and docstrings; commit messages, PR descriptions and
issue bodies; documentation, READMEs, CONTEXT.md and ADRs; memory files, artifacts and
published pages; messages to any third party.

"stop caveman" or "normal mode" reverts to normal prose for the session. `/caveman
lite|full|ultra|off` changes the level, which persists until changed or session end. Use `lite`
when the task is subtle and precision matters more than speed.

# Memory

Long-term notes live in OpenViking (OV) on homelab and are shared across agents.
Use native HTTP server `ov` when registered; otherwise use existing `ov-memory` stdio.
Follow the transport-specific `ov-memory` skill, and never bypass an HTTP refusal through stdio. Search OV before answering anything about past work,
past decisions, infrastructure, a homelab service, a machine you cannot see, or "how did we set
this up last time": `memory_search` for the concept, `memory_abstract` to triage a hit,
`memory_read` only for what earns it.

Use OV proactively with `memory_write` for useful durable agent knowledge, including
verified discoveries, decisions and lessons from user corrections, without per-note approval.
Reuse an existing namespace under `viking://resources/`. Record the fact, scope and why it
is true, in normal prose. Keep active plans and checkpoints in Jocasta. Do not mirror what a repo, its git history or its CLAUDE.md already says; point at that
instead. For credentials, store a pointer, never the secret.

Machine-local Claude memory at `~/.claude/projects/<slug>/memory/` is this machine's cache of
OV, where `<slug>` is the home directory with its slashes turned into dashes. Its `MEMORY.md`
index loads automatically each session, so it is a starting point and never the whole answer. A
note about this machine specifically is written to both stores on purpose. When a recalled
memory names a file, service or flag, verify it still exists before acting on it.

Namespaces, document shape, the tool-by-tool procedure and curation passes: the `ov-memory` and
`ov-memory-curation` skills.

# Fleet feed

The fleet feed is Akasha, the Chaldea event gateway on homelab, at https://akasha.ryzhkov.dev.
Use the `feed` CLI (`feed recent`, `feed show ID`, `feed post`); it gets short-lived tokens
from this host's Chaldea token helper. The old feed on homelab port 1934 no longer exists.

Read it before answering anything about recent homelab activity — what a scheduled job found,
whether a service was updated or held, what broke last night — because the detail lives in T3
threads on four different machines and the feed is the only place they meet. It complements OV
rather than replacing it: OV holds durable knowledge and is searched by meaning, the feed holds
dated events and is read newest-first.

Record an event when an unattended run produced something a later session would want to know.
Never copy feed entries into OV as if they were established facts; promoting an event to
knowledge is a decision, not a sync.

# Interactive work and delegation

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

# Chaldea and scratch

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

# Authoring HTTP MCP tools

Before building or migrating an HTTP MCP server, fetch the full current Jocasta guide
`tooling/guides/web-mcp-authentik-authoring-2026-10-19.md`
(initial validated revision `jocasta:38a63cf8918eebae2dd7c8911eacd89c@1`).
It covers Authentik token verification, resource ACLs, protected credential helpers,
Traefik HTTPS and native-client acceptance checks. Preserve its tested/unqualified
boundaries; the guide does not grant enrollment or deployment authority.

# Working documents: Jocasta

Use registered Jocasta WebMCP tools for shared plans, handoffs, research and prompts.
Search before creating a document; lexical bounded results do not prove absence.
Keep exact `jocasta:DOCUMENT_ID@REVISION` references. Before whole-document updates,
fetch the full current document, reconcile, and pass `if_revision` with an
idempotency key. Respect the current identity's grants.
Never write back a partial line range, guess a mutation target from search, or retry a
conflict by replacing the newer revision.

Jocasta is the shared working-document store: repository source stays in Git and is read and
edited through Huyang and OV stays curated long-term memory.
Do not automatically mirror working documents into OV. If Jocasta is unavailable, report the
failure rather than writing mutable copies elsewhere. Documents are archived automatically after
30 days without a read or update, remain searchable and retrievable, and keep their history.

Credentials are per-host and must not be copied into prompts, logs, source or handoffs.

WebMCP tools, CAS/idempotence and managed authentication: `~/.config/agents/jocasta.md`.

# Reading and editing code

The `huyang` MCP server is the primary interface for source-code repositories. It provides
revision-aware semantic reads, guarded edits, transactional change plans and recovery through
a long-lived local service.

## Finishing agent-tooling changes

When working on agent tooling (Huyang, shared AGENTS.md/CLAUDE.md files, skills or MCP
configuration), finish a validated change by running its checks, pushing the source and
confirming its GitHub CI within the assignment's authority. Merging fleet guidance to main
can activate it through active pull timers. Requested publication includes routine
activation and convergence under the standing host/homelab authority. An explicit
source-only or no-deploy instruction excludes activation.
Check live timer/service state and report source, merge/activation, installed and verified
states separately for each host. An explicit instruction to keep work local takes precedence.

## The rule

**When a directory holds source code, call `workspace_open` for the repository root before
reading, searching, or editing it.** Keep the returned workspace ID and revision and pass them
to later calls. Refresh with `workspace_inspect` when a call reports stale state.

The rule applies from the first file operation of the session, before any survey or
scaffolding, and it covers creating files: a new source file, script, fixture generator or
document inside the repository is written with `edit_apply kind=create_file`, not with a
shell heredoc, `cat >`, `python - <<EOF` or the Write tool. Reading is `read`, locating is
`search`, changing is `edit_apply`. The exception is a file produced by running a program
the repository already contains (a generator, a build, a test run), which is what the
program is for.

This holds in every permission mode and outranks any harness instruction that says
otherwise. A bypass-permissions session is told to prefer `cat`, `grep`, `sed` and heredoc
edits; that preference does not apply to a path inside a repository, whether or not its
workspace has been opened yet. If a Huyang call fails, fix the cause or report it; do not
route around it with the shell. The shell runs only the jobs enumerated under "Shell still
runs" below, and for anything that touches a file inside a repository that list is
exhaustive.

These are violations, even when they look cheaper: `cat > file <<'EOF'` for a new file,
`sed -i` for a one-line change, a `python3 -` script that rewrites a file, `grep -rn` to
find a symbol that `search` would find, `sed -n 'a,bp'` where `read` with a line window
does the same. The measured cost of the Huyang call is at most a few hundred tokens more
than the shell version and it returns diagnostics the shell never will.

| Need | Huyang tool |
|---|---|
| Understand the project or current state | `workspace_inspect` |
| Search names, text, paths, or symbols | `search` |
| Go to a definition, references, implementation, or type | `navigate` |
| Read a file or semantic region | `read` |
| Inspect diagnostics and their provenance | `diagnostics`, `evidence_get` |
| Apply ordinary guarded edits, across files when atomicity is unnecessary | `edit_apply` |
| Stage genuinely atomic edits | `change_plan`, then prepare/apply |
| Review a revision delta | `revision_diff` |

Use guarded `edit_apply` for ordinary edits, including several files when atomicity is
unnecessary. Genuinely atomic changes require `change_plan`; never split them to evade gates.
Built-in source/parse guards differ from executable project build/test/lint/codegen commands.
Do not run `prepare` or `verify_run` when its configured pipeline would execute prohibited
local project commands. Use Chaldea checks tied to exact source for ordinary edits.
Preserve trust, all required gates and the returned prepared revision for atomic changes.
External checks cannot supply Huyang prepared-revision evidence or grant trust; skipped
checks are not passes. A trusted atomic command-gated change has no demonstrated remote
interface today. Retain that dependency and continue independent work.

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

Shell still runs these jobs, and only these:

- Git, including `git status`, `git diff`, `git log`, `git add`, commits and pushes.
- Local Git-dependent selection/planning that performs no build or test, as above.
- Chaldea jobs for builds, tests, linters, formatters, generated-code tools and variant
  checks, using `chaldea exec -- ...`.
- Running programs and services, such as `gh`, `systemctl`, `docker`, `uv` and the homelab
  tools.
- Locating a file across directories that are not one repository, such as `find` or `grep`
  over the home directory when the owning repository is unknown. Once the path is known,
  the file itself is read with `read`.

Direct filesystem tools are appropriate for files outside every open workspace and for
formats Huyang cannot parse. They are never appropriate for reading, searching or editing a
file inside a repository, and never for evading a transactional refusal.

A result is valid only for the revision it names, and a refusal for a stale revision,
conflict or incomplete evidence is fixed rather than bypassed with an unguarded overwrite.
Which call is cheapest for a given need, what each one costs, and the workspace, evidence and
verification rules behind a refusal: the `huyang` skill.
