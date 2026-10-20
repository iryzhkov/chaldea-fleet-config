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

No tool-call narration. Fire calls direct, no preamble or progress note between them. Text before
a call only to warn about something destructive or resolve real ambiguity.

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

Long-term notes live in OpenViking (OV) on homelab, reached through the `ov-memory` MCP tools
and shared by every agent on every machine. Search OV before answering anything about past work,
past decisions, infrastructure, a homelab service, a machine you cannot see, or "how did we set
this up last time": `memory_search` for the concept, `memory_abstract` to triage a hit,
`memory_read` only for what earns it.

Write to OV with `memory_write` when the user asks for something to be remembered, into an
existing namespace under `viking://resources/`. Record the fact and why it is true, in normal
prose. Do not mirror what a repo, its git history or its CLAUDE.md already says; point at that
instead. For credentials, store a pointer, never the secret.

Machine-local Claude memory at `~/.claude/projects/<slug>/memory/` is this machine's cache of
OV, where `<slug>` is the home directory with its slashes turned into dashes. Its `MEMORY.md`
index loads automatically each session, so it is a starting point and never the whole answer. A
note about this machine specifically is written to both stores on purpose. When a recalled
memory names a file, service or flag, verify it still exists before acting on it.

Namespaces, document shape, the tool-by-tool procedure and curation passes: the `ov-memory` and
`ov-memory-curation` skills.

# Fleet feed

The fleet feed runs on homelab, port 1934.

Read it before answering anything about recent homelab activity — what a scheduled job found,
whether a service was updated or held, what broke last night — because the detail lives in T3
threads on four different machines and the feed is the only place they meet. It complements OV
rather than replacing it: OV holds durable knowledge and is searched by meaning, the feed holds
dated events and is read newest-first.

Record an event when an unattended run produced something a later session would want to know.
Never copy feed entries into OV as if they were established facts; promoting an event to
knowledge is a decision, not a sync.

# Interactive work and delegation

Work happens in interactive T3 sessions. Stay interactive while exploring, designing and
making decisions turn by turn. Once Igor has agreed a plan, write it to Jocasta and carry it
out in the session; do not ask again for routine work inside that agreement.
When you own orchestration of an agreed roadmap, load the roadmap-executor skill first;
a delegated worker follows its brief instead.

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
Prefer two independent reviews of the final commit, Sol 6.1 high and Opus 5.5 medium,
with the main reviewer on the other provider whenever quota allows. When quota is tight,
two different models on the same provider are allowed with fresh quota evidence and an
honestly labeled exception. One independent review is acceptable when quota or availability
prevents the pair. Follow `review-delegation` for routing and evidence. Optional Luna/Haiku
lenses need a concrete risk and a bounded target; no default swarm. Allow at most two fix
rounds. Report every reviewer's thread ID, model and verdict in the reply and a PR comment.
After an accepted review, the orchestrator verifies a change of under about 50 lines
without another review.

T3 tools act only on the host's own T3 server. There is no agent-driven launch on another
host yet; ask Igor to start work there from the T3 app.

FATE selects targets within the adopted review pair and role rules; explicit user
model overrides still apply. Use the documented outage fallback when routing is unavailable. Sonnet is excluded; Haiku is
allowed when selected. Maximum effort is high; only Luna/Haiku may use xhigh.
These are ceilings, not defaults. Choose only available live-catalog models/options;
Haiku needs an available catalog target. Never use max, ultra, ultrathink or ultracode.
Conserve Claude for required main cross-provider reviews; avoid optional Claude fan-outs.
Read a quick lookup in a known file directly.

Ask first when the estimated cost is large, the work needs operator-level access, or it
changes more than one host.

# Chaldea and scratch

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

# Authoring HTTP MCP tools

Before building or migrating an HTTP MCP server, fetch the full current Jocasta guide
`tooling/guides/web-mcp-authentik-authoring-2026-10-19.md`
(initial validated revision `jocasta:38a63cf8918eebae2dd7c8911eacd89c@1`).
It covers Authentik token verification, resource ACLs, protected credential helpers,
Traefik HTTPS and native-client acceptance checks. Preserve its tested/unqualified
boundaries; the guide does not grant enrollment or deployment authority.

# Working documents: Jocasta

Use Jocasta for shared plans, handoffs, research and prompts. Search before creating a document.
Search is lexical, so a bounded search is not proof of absence. Use exact
`jocasta:DOCUMENT_ID@REVISION` references in handoffs. Before updating, fetch the full document,
reconcile changes, and use `--if-revision N`.
Never write back a partial line range, guess a mutation target from search, or retry a
conflict by replacing the newer revision.

Jocasta is the shared working-document store: repository source stays in Git and is read and
edited through Huyang and OV stays curated long-term memory.
Do not automatically mirror working documents into OV. If Jocasta is unavailable, report the
failure rather than writing mutable copies elsewhere. Documents are archived automatically after
30 days without a read or update, remain searchable and retrievable, and keep their history.

Credentials are per-host and must not be copied into prompts, logs, source or handoffs.

Fuller guidance, including the CLI configuration: `~/.config/agents/jocasta.md`.

# Reading and editing code

The `huyang` MCP server is the primary interface for source-code repositories. It provides
revision-aware semantic reads, guarded edits, transactional change plans and recovery through
a long-lived local service.

## Finishing agent-tooling changes

When working on agent tooling (Huyang, shared AGENTS.md/CLAUDE.md files, skills or MCP
configuration), finish a validated change by running its checks, pushing the source and
confirming its GitHub CI. Fleet distribution is manual until the replacement configuration
management exists: report which hosts were updated and verified and which were not, rather
than declaring a change distributed. An explicit user instruction to keep work local takes
precedence.

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
| Apply one direct revision-guarded edit | `edit_apply` |
| Stage several related edits atomically | `change_plan`, then prepare/commit |
| Review a revision delta | `revision_diff` |

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

Shell still runs these jobs, and only these:

- Git, including `git status`, `git diff`, `git log`, `git add`, commits and pushes.
- Local Git-dependent selection/planning that performs no build or test, as above.
- Chaldea jobs for builds, tests, linters, formatters, generated-code tools and variant
  checks, using `chaldea exec --host agent-a -- ...`.
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
