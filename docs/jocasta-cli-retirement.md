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

The fleet never installs the CLI; UpKeeper does. UpKeeper PR #71 removes the
two hosts from its Jocasta consumer list, so ordinary updates stop
reinstalling it there, and every later agent_tools run removes it again.

## Root gates before merge

Merging the host_vars files activates removal at the next agent_tools run on
each host, full or narrow. Before merge, root:

1. Qualifies the installed UpKeeper capture behavior with PR #71 (or an
   already supported explicit component selection), so no update reinstalls
   the CLI on these hosts.
2. Takes a guarded backup of the binary alone, preserving its metadata, and
   validates its hash against the public Jocasta release asset it came from.
   No config or token content is read or copied.
3. Accepts review and hosted CI for the exact head.

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
guarded backup with its original owner and mode 0755 and check its hash.
