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
implementation-session. Safety-critical-code and unslop retain their validated
matching-tree migrations. Five additional links migrate only on laptop, from
.claude/skills/{codebase-design,diagnosing-bugs,grilling,resolving-merge-conflicts,tdd}
to the corresponding exact relative ../../.agents/skills/NAME target. Their
ancestors and complete trees must be real, owned directories/files and match
source recursively before any unlink. Mismatches stop all migrations. The separately
approved TDD backup/restoration is explicit, never part of an ordinary converge;
see [the restoration procedure](laptop-guidance-restoration.md).

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
Only the exact blocks in AUTHORIZED_CHANGES, QUOTA_REVIEW_CHANGES and
FATE_GUIDANCE_CHANGES in test_agent_source_migration.py may differ, as
authorized by Igor on 2026-10-18. Each replacement must occur exactly once.
The test reverses the new FATE blocks first, then the earlier quota-review,
ownership and wait changes, before comparing the unchanged historical hashes.

The plan30 completion gate aligns all three instruction entry points and
the chaldea, review-delegation and roadmap-executor skills. They call FATE
before delegation and pass its exact providerInstanceId, model and options,
including effort. Fixed-model claims survive only as the documented outage
fallback. The guidance preserves explicit overrides, cross-provider main
reviews, the strict quota exception, native T3 completion, worktree isolation
and existing budgets. Render tests exercise the real role and inventory for
all four hosts and check the installed delegation contract in both skill trees.

Merging guidance to main distributes it through active fleet pull timers.
Keep source preparation draft with auto-merge off until the parent approves
that activation. Report reviewed, merged, distributed and verified separately,
with distribution evidence for each host. This source change does not deploy
a client, restart T3 or activate AA, shared quota or automatic switching.

All other deployed bytes, destinations and the plugin bytes must match.
The Huyang role is disabled on every host and adds no deployed runtime changes.

Huyang still supplies source reads and guarded edits. Builds and tests run
through Chaldea; every Go test sets HUYANG_FRICTION=0. A separate verification
does not relax change_plan trust or prepared-revision evidence rules.
