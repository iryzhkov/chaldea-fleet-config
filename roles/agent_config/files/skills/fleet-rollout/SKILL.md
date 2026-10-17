---
name: fleet-rollout
description: >-
  Converge an authorized Chaldea fleet-config revision on agent hosts; use for
  ansible-pull rollouts, convergence verification and before/after service checks.
---

# Fleet rollout

Source/review/merge work does not authorize a deployment. Ask Igor first for
multi-host changes, credentials, homelab or Normandy deployments, UDM or NAS,
unless the exact scope is already authorized. Apply only to the named hosts.

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

## Process and outcome safety

Prefer waiting on a saved PID or a delegated thread. Never use `pgrep -f` or
`pkill -f` with a pattern that also matches the calling shell's command line.
If matching is necessary, anchor on the executable's absolute path; inspect
the match before signalling. Never kill a broad "ansible", "ssh" or "chaldea" match.

Report the exact revision, host, check/real/second-real results, snapshot diff
and verification evidence. Preserve logs and reconcile a disconnect or reboot
before retrying. Report each host separately; unattempted hosts stay unverified.
