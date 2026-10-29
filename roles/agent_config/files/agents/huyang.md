# Huyang: reading and editing code (shared agent instructions)

Maintained in chaldea-fleet-config's roles/agent_config/files/. The body combines
claude/omarchy-setup/CLAUDE.md ("Reading and editing code") and skills/huyang/SKILL.md;
keep it in sync with those role sources. Fleet is the canonical home; the old
Omarchy generator is retired. See docs/agent-instruction-ownership.md. Keep the
maintained sources aligned; do not regenerate over fleet-managed files.
Installed copies are outputs.

Tool names below are Huyang's modern MCP surface and are shared by every harness.

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

---


# Huyang: the cheapest correct call

Costs below were measured in `bench/agent-efficiency` of the Huyang repository
(cl100k tokens, Go fixture, 2026-09-12); the full table is in `docs/agent-guide.md`
there. Use these without experimenting.

- Call `workspace_open` for the repository root before the first source operation.
  Retain its workspace ID and revision, and route later reads and guarded edits by that
  ID. `root` also opens or reuses a workspace, but does not override this session rule.
  `idempotency_key` is optional; omit it unless you will retry the same call.
- Change text you know (a line, a block, a local rename): `edit_apply` with
  `operation.kind=replace_literal`, `old`, `new`, optional `path`, and
  `expected_count` when the text occurs more than once. One call, about 70 request
  and 300 response tokens for a one-line change; the response carries the changed
  locations, the new revision and the diagnostics the edit caused, and never echoes
  your text (no patch unless `verbose`). Do not search first.
- New file: `edit_apply` with `kind=create_file`, `path`, `content`. One call; an
  existing path is refused with its `revision_id`, and `replace=true` with that
  revision overwrites it. Several edits at once: `edit_apply` with `operations=[...]`
  (every kind but replace_range, applied in order, one call; a refusal stops the list
  and earlier operations stay, so use `change_plan` for anything atomic).
- Move, copy or delete a file: `edit_apply` with `kind=move_file` (`from`, `to`),
  `kind=copy_file` (`from` may be an absolute path outside the repository, `to`) or
  `kind=delete_file` (`path` plus `revision_id` or `expected_sha256`). The bytes never
  pass through your context and are never reformatted. Huyang does not touch the Git
  index: the reply's `git` block gives each path's tracked state and `next` names the
  `git add` to run so Git records a rename; run it. Never `cp`, `mv` or `rm` inside a
  repository.
- References, definition, implementations or callers of a symbol: `search` with
  `query=Name` and `mode=references` (or `navigate` with `relation` and `symbol=Name`).
  No path needed; the name is resolved to its declaration first. Without a language
  server the search answers literal matches and says so.
- Read a file: `read` with `target.path`; a region: `start_line`/`end_line` (no cap) or
  `target.symbol_locator` (Go and Python resolve without a language server); several
  files: `targets`; `numbered=true` when you need line numbers. One call each; a whole
  file costs less than the built-in Read. A file over about 500 lines: `view=outline`
  first, or `max_lines` (per call or per target); a capped reply says `truncated` with
  the total, and a multi-target reply lists every target's size under `entries` before
  the bodies.
- Locate text: `search` (literal by default, whitespace-exact for multi-line queries)
  with `paths` (globs or substrings) to scope and `context_lines` for the surrounding
  numbered lines, which replaces `grep -rn -C` and the read after it. Hits carry handles
  for `edit_apply kind=replace_range` when a target cannot be named by content.
- Build and test: use a Git-independent make target or selected test command through
  `chaldea exec -- ...`. For every `go test`, set `HUYANG_FRICTION=0`
  inside the job, for example:
  `chaldea exec -- env HUYANG_FRICTION=0 go test ./...`.
  Read the `chaldea` skill for snapshot, scratch and job-result rules. Huyang handles
  source reads and guarded edits; Chaldea supplies build/test execution.
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
- Several files that must change atomically: `change_plan` (prepare, then apply).
- A file outside any repository (config, script, note, a lone source file): no
  `workspace_open` needed. `read` with the path, and `edit_apply` (`replace_literal`,
  `create_file`, `move_file`, `copy_file` or `delete_file`) with absolute paths and no
  `workspace_id`, open a documents workspace implicitly and return its id for further
  edits. Files that are not source and live outside any repository, such as the
  machine-local memory notes under `~/.claude/projects/`, may be written with either
  `edit_apply create_file` or the harness `Write` tool; both are one call and neither
  gains diagnostics there.

Go files are gofmt-formatted after every edit unless `format=false`. Pass `verbose=true`
to `edit_apply` only when you need the full change record and handle resolution.

## Workspace and verification constraints

Huyang can keep several explicit workspaces open. Always route by workspace ID; do not
assume the current directory identifies the intended workspace. A result is valid only
for the revision it names.

Use semantic handles or exact revision-bound locators when available. Ordinary guarded
`edit_apply` edits may cover several files when atomicity is unnecessary. Genuinely atomic
changes require `change_plan`: inspect its evidence and apply only its returned
`prepared_revision`. Never split an atomic change to evade checks. If Huyang reports a
conflict, stale revision, incomplete evidence or recovery requirement, resolve it rather
than bypassing it with an unguarded overwrite.

`change_plan` prepare retains its sandbox pipeline: `format_gate`, parser, check and tests.
Built-in source/parse guards are distinct from executable project build/test/lint/codegen
commands. At qualified Huyang revision b6ba774, prepare invokes its pipeline locally.
Project commands declared by `.huyang.toml` or detected from the repository run only when
trusted by user policy in `~/.config/huyang/config.toml`. Do not run prepare or `verify_run`
when that pipeline would execute prohibited local project commands. Ordinary guarded edits
use Chaldea checks tied to exact source instead. An untrusted root's skipped commands are
missing evidence, never passes. Do not auto-trust a root or relax required gates.
Chaldea results neither grant trust nor supply Huyang prepared-revision evidence.
A trusted atomic command-gated change currently has no demonstrated remote-compatible
interface. Retain the affected dependency and continue independent authorized work.
See docs/agent-instruction-ownership.md for qualification source references.

Diagnostics and test claims are evidence-bound. Distinguish affected-test coverage from a
full test run, and treat provisional or partial evidence as such. Report the tested source
revision, command, host and job outcome; a deferred or uncertain job is not a passing check.

The native text path works without Neovim. Semantic navigation, formatting and LSP
diagnostics additionally depend on the corresponding parser, language server or formatter
being available.
