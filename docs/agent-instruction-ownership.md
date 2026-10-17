# Shared instruction ownership

OpenCode's Huyang V2 plugin has a separate narrow installation seam. Omarchy owns its
source, and `agent_config` installs the reviewed copy without changing OpenCode JSON,
other plugins or the wrapper. See [OpenCode Huyang profiles](opencode-huyang-profiles.md)
for supported version, paths, guards and deferred integration checks.

The `agent_config` role owns installed shared instructions and fleet skills. Edit
`roles/agent_config/files/`, not installed files. Its defaults map source paths to
destinations; its tasks copy those reviewed bytes directly.

Fleet skills are registered in `agent_config_skills` and installed in
`~/.claude/skills` and `~/.agents/skills` for Claude, Codex and OpenCode.
Supporting files travel with each skill. Keep ordinary sessions free of extra
startup ceremony; roadmap execution and audit workflows load on demand.

The role retires only these exact real directories: find-skills,
improve-codebase-architecture, domain-modeling, prototype, code-review and
implementation-session. Symlinks, regular files and unrelated skills stay.
`synced` is an unmanaged sync store, not a skill.

Only safety-critical-code and unslop may migrate from existing symlinks.
Before unlinking either, the host-side role requires a directory target and a
recursive match with the managed source, including supporting files and extra
entries. A mismatch or any other managed-skill symlink stops installation.
Every candidate is validated before any link is removed; check mode compares
without unlinking. The target is preserved when the link becomes a managed copy.

For Huyang, keep these role inputs consistent:

- `agents/AGENTS.md` contains the resident summary.
- `codex/AGENTS.md` contains that same summary inside the fleet fence.
- `claude/omarchy-setup/CLAUDE.md` contains the detailed reading/editing rule.
- `skills/huyang/SKILL.md` contains the tool workflow and prepare/trust constraints.
- `agents/huyang.md` combines the role's Claude reading/editing section and skill
  body, without skill front matter.

Omarchy still carries overlapping bootstrap/policy sources in
`config/claude/CLAUDE.md`, `config/claude/skills/huyang/SKILL.md` and
`config/bin/agents-instructions-gen`. Update shared Huyang guidance there in the
same window. Its `docs/agent-instruction-ownership.md` documents the overlap.
Do not run that generator over fleet-managed installed files or copy its entire
resident output over these role inputs: the repositories have different publishing
and delegation rules that must be preserved. Other ownership migration is separate.

Huyang supplies source reads and guarded edits. Builds and tests use the repository's
commands through `chaldea exec --host agent-a`; every Go test sets
`HUYANG_FRICTION=0` inside the job. `change_plan` prepare still owns its sandbox
format/parser/check/test gates, project-command trust and prepared revision evidence.
Independent Chaldea verification does not relax those gates.

`tests/test_huyang_instructions.py` checks the maintained copies without installing
anything. Run checks and any generation only in isolated Chaldea jobs with disk-backed
scratch and a disposable HOME. Source synchronization does not deploy or prove convergence.
