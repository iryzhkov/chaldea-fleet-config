# Huyang releases and host activation

The huyang role is off by default, explicitly off for all four agent hosts,
and runs before MCP registration. This PR deploys no Huyang service changes.
The first release must be published from merged Huyang main by the orchestrator;
this change creates no tag. Do not enable a host before reviewing both assets.

Set huyang_version and huyang_sha256.x86_64 / .aarch64 in
inventory/group_vars/all/main.yml. Each digest pins the entire matching
huyang-linux-x64.tar.gz or huyang-linux-arm64.tar.gz archive. Embedded
manifest.json must match the version, architecture and every runtime file hash.
The archive verifier refuses links, duplicates, unsafe paths, unlisted files,
drifted immutable releases and unsafe managed directory components.

On activation, the existing ~/.local/share/huyang Git checkout is renamed to
~/.local/share/huyang.pre-fleet. A pre-existing backup or unknown layout stops
migration. State stays at ~/.local/state/huyang and the trust policy at
~/.config/huyang/config.toml is never read or written by this role.
An installation using a different state path must set huyang_state_dir to
its existing path before activation. The old checkout is retained intact.

Releases install in ~/.local/share/huyang/releases/TAG. A verified release
switches current by a same-directory rename. previous retains the former
release and older releases are never pruned. A compatibility bin link serves
existing OpenCode settings while Claude/Codex registrations select
current/bin/huyang when enabled. Disabled hosts retain their existing command.

The managed unit clears inherited runtime-path overrides. Huyang discovers the
Lua kernel beside its running executable, so the binary and kernel remain
paired when current changes before a restart. The role provisions its separate
diagnostic toolchain and headless init, leaving the personal Neovim config alone.
See [the toolchain contract](huyang-toolchain.md).
huyang_languages defaults to the strict suite's nine languages. Inventory
can omit java or rust on a memory-constrained host. MemoryHigh is explicit
per host: agent-a 4G, agent-b 2G, omarchy-pc 2G, laptop 1G.

Only a changed release pin creates restart intent. A failed restart retains
that intent. A successful restart replaces it with pending health evidence;
a later health retry does not restart again. Check mode performs no install,
migration, service operation or MCP health request. Steady converges make no
MCP calls, so they do not replace active workspace providers with health samples.
Unit configuration changes, including huyang_socket, require a release pin bump
to take effect in the running service. A toolchain current switch is visible to
new providers immediately; existing providers keep their loaded processes.
After restart the role waits for the socket and calls workspace_inspect and
language_server_status for every selected language using controlled samples.
It checks required server executables and reports expected languages. Missing
required servers fail the language presence gate. Provider capacity delays keep
health pending for the next converge, without another restart or a false missing
server failure. Slow initialization and unrelated project diagnostics do not
fail the presence gate. A pending retry probes all selected languages again
and may replace idle workspace providers until verification completes.

## Orchestrator commands

First merge the reviewed release workflow, tag merged Huyang main, then publish
and review its assets. In a separate fleet PR, fill the release pins and change
only the selected host's huyang_enabled to true. All hosts remain disabled here.
Optional per-host huyang_languages and huyang_memory_high belong in hosts.yml.

Run the following on each selected host, replacing APPROVED_ENABLE_SHA with
that host's merged enable commit. Use one host at a time; do not run these
commands as part of source implementation.

```sh
# Choose exactly one inventory host on its own machine:
# agent-a | agent-b | omarchy-pc | laptop
fleet_host=agent-a
fleet_revision=APPROVED_ENABLE_SHA
export TMPDIR="$HOME/.cache/chaldea-scratch/agent-tooling/converge-$fleet_host"
mkdir -p "$TMPDIR"
pull() {
  "$HOME/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-pull" \
    --url git@github-chaldea-fleet-config:iryzhkov/chaldea-fleet-config.git \
    --checkout "$fleet_revision" \
    --directory "$HOME/.local/share/chaldea/fleet-config" \
    --limit "$fleet_host" --tags huyang,mcp_registrations "$@" site.yml
}
systemctl --user status huyang.service --no-pager >"$TMPDIR/before.txt"
pull --check --diff >"$TMPDIR/check.log" 2>&1
# Review check.log. Stop on unexpected differences, then run:
pull >"$TMPDIR/first.log" 2>&1
pull >"$TMPDIR/second.log" 2>&1
# Require the second recap: changed=0, failed=0, unreachable=0.
systemctl --user status huyang.service --no-pager >"$TMPDIR/after.txt"
readlink "$HOME/.local/share/huyang/current"
```

Repeat with fleet_host=agent-b, fleet_host=omarchy-pc and fleet_host=laptop on
their respective hosts, only after each host's reviewed enable commit.
For rollback, restore the previous exact version/digest pin and converge through
the same check/real/second-real sequence. The old release is still installed.
