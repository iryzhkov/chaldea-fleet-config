---
name: fleet-rollout
description: >-
  Converge an authorized Chaldea fleet-config revision on agent hosts; use for
  ansible-pull rollouts, convergence verification and before/after service checks.
---

# Fleet rollout

Source-only work does not authorize fleet activation. A main-branch merge can
activate guidance through active pull timers; inspect live timer/service state.
Retain existing deployment authority without asking again for routine convergence.
Ask only when concrete new multi-host, credential or deployment scope is needed.
Apply only to authorized hosts and report activation and installed verification separately.

## Pin and run on the host itself

- Record the approved repository revision, target hosts and expected changes.
  Use the pinned ansible-pull, not a system Ansible or a moving checkout.
- Keep scratch/logs under `~/.cache/chaldea-scratch/rollout-<date>/` on each
  target; set TMPDIR there, never `/tmp`. Keep credentials out of logs.
- Use one batched SSH call per host: ufw rate-limits repeated SSH connections.
  Run the complete snapshot/check/real/second-real/verification sequence on
  that host itself. Do not run the play against a live host from a test fixture.
- Run long converges asynchronously in a T3 delegated thread and rely on its
  single completion notification. For an existing non-child thread, register
  one Chaldea thread wait instead. Never add polling or a second watcher.

Set `fleet_host`, `fleet_revision` (the approved commit) and `rollout_scratch`
to verified values in the host-side script. The pinned invocation is:

```sh
export TMPDIR="$rollout_scratch"
mkdir -p "$TMPDIR"
pull() {
  "$HOME/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-pull" \
    --url git@github-chaldea-fleet-config:iryzhkov/chaldea-fleet-config.git \
    --checkout "$fleet_revision" --directory "$HOME/.local/share/chaldea/fleet-config" \
    --limit "$fleet_host" "$@" site.yml
}
snapshot() {
  for manager in system user; do
    systemctl "--$manager" list-units 'chaldea*' --all --no-pager
    systemctl "--$manager" list-unit-files 'chaldea*' --no-pager
    systemctl "--$manager" list-timers 'chaldea*' --all --no-pager
  done
}
snapshot >"$TMPDIR/before.txt"
pull --check --diff >"$TMPDIR/check.log" 2>&1
```

Review the check diff against approved scope before the real run. Stop on an
unexpected change or failure. Then run `pull` twice with separate logs; require
both exit statuses to pass and the second recap to report `changed=0`,
`failed=0` and `unreachable=0`. Do not hide failures behind a pipe to tee.
Capture `snapshot >"$TMPDIR/after.txt"` and
`diff -u "$TMPDIR/before.txt" "$TMPDIR/after.txt"`; explain the differences.
Verify expected installed versions, unit states and timer schedules.

## Guidance-only convergence

For an authorized guidance-only change, use canonical `site.yml --tags agent_guidance`
with an explicit JSON extra-vars file selecting `agent_config_files`,
`agent_config_skills` and `agent_config_skill_dirs`. Select only approved MD
destinations and complete changed skill trees. Empty lists mean no selected files
or skills. Review the selection against role defaults at the pinned revision.

This tag runs parent-directory creation, selected file copies and canonical
guarded skill installation. It skips retirement, the OpenCode plugin, generated
fleet-tools and other roles. Fact gathering and the actual-host identity
assertion still run. Do not use `--skip-tags always` or override
`expected_hostname` to defeat that assertion. Without tag selection, ordinary
full-role behavior is unchanged.

Use the pinned pull function above with the selected vars:

```sh
pull --tags agent_guidance --extra-vars "@$rollout_scratch/selected-guidance.json" \
  --check --diff >"$TMPDIR/guidance-check.log" 2>&1
# After scope review, repeat without --check twice, keeping separate logs.
```

Pinned ansible-pull 2.19.14 rejects `--start-at-task`; do not use it.
Its retrieval play must match the actual local hostname separately from the
canonical inventory alias. On laptop, use `-i inventory -i localhost,` for
retrieval and keep `--limit laptop` for the site play. The site still checks
the actual hostname against inventory's `expected_hostname`. A retrieval
rejection is not a successful check and must be resolved before applying.

Back up the selected installed files and complete skill trees, preserving
metadata, before REAL. Inspect CHECK's task list and diff against the selected
scope. On a fresh home, check mode can defer a copy when its parent does not
yet exist; document that gap rather than calling it verified. After REAL and
second REAL, verify complete installed tree membership, bytes, file modes and
directory modes against the exact approved source. Require second REAL
`changed=0 failed=0 unreachable=0`, and compare service/timer snapshots as above.
Do not broaden convergence to resolve a narrow-path failure without authority.

The prior four-host narrow composition is retained at
`/home/igor/.cache/executor-autonomy-review-20261020/rollout/guidance-v2-evidence.json`,
including CHECK/REAL/second-REAL and installed-tree receipts. It used an absolute
scratch playbook with the same canonical guarded install import. Those receipts
prove that prior composition, not a later revision or host state. The canonical
tag path has separate synthetic scope, refusal and idempotence checks.

## Process and outcome safety

Prefer waiting on a saved PID or a delegated thread. Never use `pgrep -f` or
`pkill -f` with a pattern that also matches the calling shell's command line.
If matching is necessary, anchor on the executable's absolute path; inspect
the match before signalling. Never kill a broad "ansible", "ssh" or "chaldea" match.

Report the exact revision, host, check/real/second-real results, snapshot diff
and verification evidence. Preserve logs and reconcile a disconnect or reboot
before retrying. Report each host separately; unattempted hosts stay unverified.
