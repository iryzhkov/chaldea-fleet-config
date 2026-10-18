# Laptop guidance restoration

Igor approved "Back up and restore canonical TDD" on 2026-10-18 after the
guidance-only rollout stopped on five existing laptop links. Source preparation
does not run this repair. The parent must accept the new head, green CI and the
merged pin before any laptop write. The other three hosts are already verified.

The exact permitted input is ~/.agents/skills/tdd/SKILL.md, SHA256
cb01f66bebfaa25fa1f88e6b7e769cd9fd9f35b1120b8563749820738814c927.
It must equal the pinned canonical source plus the single 149-byte UTF-8 footer
about refactoring and the retired code-review skill. Canonical SHA256 is
15c3a204ee9e926ffe14e5e02ab06e2773bdc9507be019ad18dc38d325316ce5.
Any other input, wrong owner, broken/unexpected link or unsafe ancestor stops.
There is no generic local-content exception.

Run the explicit tools/restore-laptop-tdd.yml play from the parent-verified merged
checkout, with the laptop inventory and pinned Ansible 2.19.14. It first verifies
the recorded .claude/skills/tdd -> ../../.agents/skills/tdd link and all owned
target ancestors/tree. It verifies the original hash, exact footer and pinned
source hash before creating any backup. No link is removed by this play.

Backup is ~/.cache/chaldea-scratch/rollout-guidance-20261018/tdd-before-canonical/.
The destination must be absent. SKILL.md preserves original content, owner, group,
mode and timestamps through cp --archive. metadata.json records the original
Ansible stat metadata including checksum. The play requires backup hash, owner,
group, mode and mtime equality before normal Ansible copy restores canonical
source. A full recursive source/target comparison then verifies the restored
tree. The backup remains. An existing backup or an already-restored input
requires inspection, not an automatic overwrite/retry.

Follow fleet-rollout's single batched host-side sequence with real operator HOME,
actual id -u and disk TMPDIR under the rollout scratch. Detect and wait for any
active ansible-pull first. Use a task-owned checkout and fetch the exact approved
object, never substitute moving main. Confirm Git HEAD before each operation.

For the explicit restoration step, the command shape is:

```sh
export TMPDIR="$HOME/.cache/chaldea-scratch/rollout-guidance-20261018"
playbook="$HOME/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-playbook"
# Set checkout to the task-owned repository at the parent-verified merged SHA.
ANSIBLE_CONFIG="$checkout/ansible.cfg" ANSIBLE_ROLES_PATH="$checkout/roles" \
  "$playbook" -i "$checkout/inventory" --limit laptop \
  "$checkout/tools/restore-laptop-tdd.yml" --check --diff
# Inspect the exact restoration diff, then repeat without --check.
```

Record service/unit/timer snapshots, runtime versions/artifact hashes and installed
hashes before restoration. Inspect the restoration check, run it once for real,
and verify preserved backup and canonical TDD hash. Then run pinned ansible-pull
at the same accepted merged revision with --limit laptop --tags agent_config
--check --diff. Inspect its diff before real apply. Run real apply twice; require
the second recap `changed=0 failed=0 unreachable=0`. The seven validated links
become managed directories only after every link validation passes. Existing
canonical .agents target bytes must remain unchanged by that migration.

Verify all 65 managed installed hashes against the accepted source, including
AGENTS.md/CLAUDE.md and both relevant skill trees. Compare after snapshots and
explain independent timer firings. Preserve logs and the backup; report exact
pin, all statuses and actual installation evidence. No runtime upgrade, key,
credential/binding/grant, role enable, service/MCP/T3 restart or other-host action
is included. Keep the parent's canonical completion gate open until its report
review is complete.
