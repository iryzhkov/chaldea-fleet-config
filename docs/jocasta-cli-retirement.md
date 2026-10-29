# Jocasta CLI retirement on the laptop and omarchy-pc

Ordinary agents use the Jocasta MCP server. The legacy `jocasta` CLI binary in
`~/.local/bin` is retired on the laptop and omarchy-pc only, through the
existing agent_tools task "Remove commands of retired tools".
`inventory/host_vars/{laptop,omarchy-pc}/jocasta-cli-retirement.yml` add
`jocasta` to that host's `agent_tools_retired_commands` and keep every command
of the role default.

Unchanged by this selection:

- `~/.config/jocasta` (config and token) on both hosts, the credential check
  that stats the token, and the backend's static-token map. Credential cleanup
  is a separate, explicit decision.
- agent-a and agent-b, which have no CLI installed, and the homelab and
  Normandy operator clients, which stay maintained. Their retired list is the
  role default.
- Every other agent_tools task and every other role.

Chaldea fleet-config manages the current agent environment and enforces this
retirement. The old binary came from UpKeeper. No UpKeeper binary or units
were present on the retirement targets or at the documented controller
locations; its legacy manifest cleanup in PR #71 was independent of this
rollout. Every later agent_tools run keeps the CLI absent.

## Completed rollout and evidence

PR #130 merged as `34f1c853aa354fce2de7dd995efa68a432e8f868` on
2026-10-28. Root reviewed the full CHECK diff on both targets: only `jocasta`
would be removed. Each REAL reported `ok=3 changed=1 failed=0 unreachable=0`,
and each repeat reported `changed=0`. Both executables were independently
verified absent. Other bin entries, Jocasta credential metadata, profiles,
current/previous links and waits service identities were preserved.

Before merge, root verified the active deployment owner and absence of a
known automatic UpKeeper installer, accepted both final source reviews and
all six hosted checks, and revalidated guarded binary-only rollback copies.
The copies match exact installed bytes and the retained UpKeeper manifest
pins. The original public release asset is unavailable: this is installed-state
rollback evidence, not independent release provenance. Config and token
contents were neither read nor copied.

Execution `0010e140a7e8444483739845c3e6fc2d` completed its applies/repeats by
14:03:45Z and closed with explicit shared-window release at 14:12:02Z,
`remainingCleanup=[]`. The scoped decision check is
`jocasta:2de2223c9a659e327f00b0783c34a357@1`; the operative checkpoint is
`jocasta:405dc259d4563fba09a7f2aa9fa6d58e`. A/B were already CLI-absent;
this rollout does not turn their deferred native/provider tests into passes.

Merging a host's retirement selection activates removal at its next
agent_tools run. A future rollout still needs actual installer/dependency
checks, a guarded backup, source acceptance, fresh host admission and full
CHECK review before applying; this closeout grants no additional authority.

## Narrow run

Use the pinned `pull` function from the fleet-rollout skill, with that
skill's scratch, logging and laptop retrieval rules, on each host itself:

```sh
pull --tags agent_tools_retired_commands --check --diff >"$TMPDIR/retire-check.log" 2>&1
# After reviewing the CHECK diff: two real runs, separate logs.
pull --tags agent_tools_retired_commands >"$TMPDIR/retire-real.log" 2>&1
pull --tags agent_tools_retired_commands >"$TMPDIR/retire-repeat.log" 2>&1
```

The tag runs only the removal task, plus fact gathering and the always-tagged
actual-host identity check. Do not use `--skip-tags always` or override
`expected_hostname`. CHECK may change only `jocasta` and any default retired
command still present; the repeat must report
`changed=0 failed=0 unreachable=0`. Then verify `~/.local/bin/jocasta` is
absent and the metadata of `~/.config/jocasta` and of other `~/.local/bin`
entries is unchanged. `tests/test_agent_tools_retirement.py` covers scope,
cohort, refusal and idempotence against a scratch home.

## Rollback

Revert the host's `jocasta-cli-retirement.yml` on main first; otherwise the
next agent_tools run removes the CLI again. Then restore the binary from the
guarded backup with the metadata it preserved and check its hash.
