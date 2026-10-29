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

## Standing operator authority

Igor adopted standing authority for agents to modify existing hosts and homelab
infrastructure for requested outcomes on 2026-10-29. The shared entry points own
that policy; executor, planning, rollout and Chaldea skills refer to it. Explicit
task restrictions still win. Ordinary Chaldea exec examples omit host selection.
The exact changed guidance blocks are recorded in agent_config_operator_autonomy.json;
source migration reverses this layer first and retains all historical fixtures.
This change does not implement remote Huyang atomic verification or alter access ACLs.

## Lightweight interactive delegation

Igor adopted lightweight delegation and proportional execution guidance on 2026-10-29.
All three entry points keep evolving objectives, decisions and integration with the parent,
while bounded children contain detail-heavy work. Ordinary delegation does not select the
roadmap lifecycle. Review-delegation owns the mechanics, direction changes, durable review
evidence and the necessity check applied during execution. Optional design and qualification
work must serve a current requirement or evidenced risk; required checks remain binding.
Routine notifications are batched, with material changes and requested status surfaced
promptly. Claude's no-progress-note rule was narrowed to permit these approved updates;
its other style preferences are unchanged. Exact review IDs, models, verdicts and commits
remain in durable receipts, with short verdicts and links in chat.
The exact reversible layer is agent_config_interactive_delegation.json. Historical
fixtures stay unchanged. This layer adds no runtime, scheduler or access changes.

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

Merging guidance to main can activate it through active fleet pull timers.
Standing host/homelab authority covers routine activation for requested outcomes.
An explicit source-only or no-deploy instruction excludes activation; keep such work
draft with auto-merge off. Check current timer/service state before publication. Report reviewed, merged, distributed and verified separately,
with distribution evidence for each host. This source change does not deploy
a client, restart T3 or activate AA, shared quota or automatic switching.

The adopted consistency layer, jocasta:b491ec8b880f1ef2d597a3a016e59ce3@2,
is recorded as exact before/after blocks in agent_config_guidance_consistency.json.
Render tests reverse this layer before all earlier layers, preserving the original
byte baseline. The historical laptop TDD input and canonical hashes stay pinned;
restoration verifies that input before copying today's accepted skill source.
Use fleet-rollout's canonical agent_guidance tag and selected file/skill variables
for scoped guidance convergence. All other deployed bytes, destinations and the
plugin bytes must match.
The Huyang role is disabled on every host and adds no deployed runtime changes.

Huyang still supplies source reads and guarded edits. Builds and tests run
through Chaldea; every Go test sets HUYANG_FRICTION=0. Ordinary guarded edit_apply changes may span files when atomicity is unnecessary.
Genuinely atomic changes still require change_plan and its trust/gate/prepared-revision
evidence. Do not run prepare or verify_run if its configured pipeline would execute
prohibited local project commands. External Chaldea checks cannot attest Huyang's
prepared revision, skipped checks are not passes and roots must not be auto-trusted.
The trusted atomic command-gated case remains an explicit dependency, with no
demonstrated remote-compatible interface.

This execution boundary was qualified against Huyang b6ba774. Prepare invokes local
pipeline stages in internal/providerpool/stagers.go lines 296-304; command execution
is local in internal/workspace/pipeline.go lines 729-732, with the trust skip at line
672. This guidance corrects the instruction conflict without claiming runtime support.
