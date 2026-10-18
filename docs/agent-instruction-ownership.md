# Shared instruction ownership

chaldea-fleet-config is the canonical home for agent tooling. Omarchy setup
only bootstraps a fresh desktop. Edit role sources, never installed copies.

The agent_config role copies the maintained instruction files and complete
skill trees from roles/agent_config/files/. Its defaults map every destination.
The historical claude/omarchy-setup path stays in place because existing
host-local Claude imports name it. That path no longer describes ownership.

The OpenCode Huyang plugin is a fleet-owned file at
roles/agent_config/files/opencode/huyang-profiles.js. Installation uses copy,
with the same collision and symlink guards. It no longer fetches from Omarchy.
Its bytes match the former ebec80b source, SHA-256
e46883992727741758115492030f75bb26dbea14dccd3a4b4c3459cc5547f6c4.
See [the plugin contract](opencode-huyang-profiles.md).

Fleet skills install in ~/.claude/skills and ~/.agents/skills. Existing unrelated
skills stay unmanaged. Retirement remains limited to find-skills,
improve-codebase-architecture, domain-modeling, prototype, code-review and
implementation-session. Only safety-critical-code and unslop can migrate
validated, recursively matching symlinks; mismatches stop before any unlink.

The maintained Huyang reference combines the Claude reading/editing section
and Huyang skill body. Keep these sources aligned manually. The old Omarchy
generator and obsolete Steward projection are retired; they are not needed
to install these directly maintained sources.

The laptop/reaper utilities, Claude settings and third-party skills list are
preserved under tooling/legacy-bootstrap/. No task installs them in this change.
Their historical tests and laptop isolation document travel with them.

## Byte compatibility

tests/fixtures/agent_config_before.json records all source hashes from fleet
main 7185b506, plus the former downloaded plugin hash. The render test installs
the agent_config role for agent-a, agent-b, omarchy-pc and laptop into disposable
homes, and compares every managed file and skill against this baseline.
Only the exact blocks in test_agent_source_migration.py's AUTHORIZED_CHANGES
may differ, as authorized by Igor on 2026-10-18. Each replacement must occur
exactly once and is reversed before comparison with the unchanged historic hashes:

- agents/jocasta.md lines 3-4 now identify the maintained fleet source.
- agents/ov-memory.md lines 3-5 now identify fleet sources and aligned skills.
- agents/huyang.md lines 5-8 replace the obsolete Omarchy generator overlap
  claim with fleet ownership and the retired-generator note.
- skills/chaldea/SKILL.md adds the optional wait-description guidance and the
  description argument in the existing CLI example.

All other deployed bytes, destinations and the plugin bytes must match.
The Huyang role is disabled on every host and adds no deployed runtime changes.

Huyang still supplies source reads and guarded edits. Builds and tests run
through Chaldea; every Go test sets HUYANG_FRICTION=0. A separate verification
does not relax change_plan trust or prepared-revision evidence rules.
