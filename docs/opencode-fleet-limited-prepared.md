# Limited OpenCode on agent-a, agent-b and omarchy-pc: prepared selection

Source preparation only. `docs/examples/opencode-fleet-limited.yml` is outside
inventory and no role loads it, so a normal pull or converge changes nothing.
No enrollment, credential delivery, runtime or native staging, profile
delivery, T3 provider change, waits migration or session has happened because
of this file.

## What is prepared

For each of the three hosts, exactly one preset, enrollment and profile named
`jocasta-tooling-opencode`. They are the laptop's reviewed OpenCode entries
with only host-local facts changed. No Claude or Codex limited profile is
prepared for these hosts, and the laptop's three profiles are unchanged.

- Waits: `chaldea_client_waits_service_mode: system`, persistent (no
  deadline), runtime root
  `/home/igor/.local/share/chaldea/releases/client-v0.4.20`. That is the
  separately staged published release (archive SHA-256
  `ed3376ab8f21c1b6bb7b2d03e9e8c074dd43ed25be4881aafe574a12e8b618ff`,
  manifest SHA-256
  `c8542918859a19ec99065117c5bd359a12de1838d6f54a4090f5e1ee12a2d2d1`), never
  the shared `current` link. `chaldea_node_version` keeps its shared 26.10.0
  and `chaldea_client_waits_legacy_user_node_version` stays unset, so the
  ordinary strict owner admission in `roles/chaldea_client/tasks/waits-owner.yml`
  accepts an exact role-rendered user unit, active or inactive, and the
  maintained migration in `waits-system.yml` stops, preserves and masks it
  before the system unit starts. No guard is extended. Retention keeps
  pruning; it protects 26.10.0 because that stays the pinned version.
- Ceiling and preset: project `tooling`, 1800 seconds, `delegate: false`,
  audience `jocasta` with `get`/`history`/`list`/`search` on
  `project:tooling`, model `opencode/big-pickle` with no options, instance
  `opencode-jocasta-tooling`, the laptop's reporter prompt.
- Enrollment: the existing Jocasta tooling provider, one ordinary account per
  host, `chaldea-<host>-jocasta-tooling-opencode`, 300-second tokens, app
  password at
  `/home/igor/.config/chaldea/authentik/jocasta-tooling-opencode.app-password`.
- Profile: the protected x86-64 OpenCode 2.1.3 native from
  `@opencode/cli-linux-x64` 2.1.3 (archive SHA-256
  `c251bb3962813919d5eb8c0f43cd1cb3ab1d7a0cd28b2e556985706413005cb0`, member
  `package/bin/opencode`): SHA-256
  `4c2630769fa853343a781e765b2280fc1a07f33f7c10d484f75d59e61eb85bc3`, 240306352
  bytes, ELF machine 62, at
  `/home/igor/.local/share/chaldea/provider-assets/opencode/2.1.3/opencode`.
  Private home and tmpdir under
  `/home/igor/.local/state/chaldea/profiles/jocasta-tooling-opencode/`, cwd
  `/home/igor`, MCP server `jocasta_tooling`.

The tool allowlist and prompt are not the authorization boundary; the Jocasta
verifier and the token's project claim are.

## Preserve staging through normal pulls

The per-host `chaldea-staging-retention.yml` files retain `client-v0.4.20`
while these hosts still converge the ordinary user-mode client. Without that
explicit retention, the next normal pull removes the inactive staged release
before system-mode activation. These files use the existing bounded rollback
list, preserve each host's installed rollback history and current/previous,
and neither install absent versions nor select a service or profile. The
shared list, six-version ceiling and cleanup tasks remain unchanged. Recheck
installed rollback versions before merging, and verify the runtime still
exists after a normal converge before accepting final readiness.

## Bindings root supplies

Each host's selection needs host-local IDs read from that host's own T3
server. They are `null` in the prepared file, and composition refuses while
any is null, malformed, equal to a laptop ID or shared with another host:

- `caller_destination`: the caller project allowed to start the session.
- `session_project`: the dedicated session project (preset `projectId`).
- `waits_environment`, agent-a and agent-b only: the T3 environment ID system
  waits serves. Source declares none for these two hosts; the role's own
  public validation refuses a session policy without one. omarchy-pc keeps
  its inline `94023493-6346-46a6-8ca0-3c7d7ef28644` in `hosts.yml`.

The tests use explicit synthetic per-host IDs only.

## Final integration

Once the bindings and the other gates are ready, root writes
`inventory/host_vars/<host>/chaldea-jocasta-tooling.yml` for each host equal
to `compose(host, bindings)` in `tests/test_opencode_fleet_limited.py`, and
replaces the inert-data assertions with real-inventory ones. The existing
laptop test, which requires every other host to lack these keys, changes in
the same commit. Then come the source review pair, CI and the PR.

Gates before any merge, all root-owned:

1. client-v0.4.20 staged at the runtime root on each host, and proof that it
   runs under Node 26.10.0 there. That compatibility is not yet proven.
2. Exact characterization of each host's current user waits unit (bytes,
   metadata, manager state) and of the backup path the migration reserves.
3. The x86-64 native staged at the asset path and rechecked by size and
   SHA-256; private 0700 home and tmpdir provisioned; model and provider
   authentication qualified in that home.
4. The three accounts enrolled through homelab-infra under its existing-only
   provider gate, each app password delivered only to its own host.
5. The provider instance `opencode-jocasta-tooling` registered on each host
   with binaryPath `/etc/chaldea/sessions/jocasta-tooling-opencode/exec`.
6. Native acceptance per host: tooling read, other-project denial, exact
   service/helper/provider identity, status, completion and cleanup.

Rollout order is agent-a, agent-b, then omarchy-pc, checking each before the
next. Rollback for one host removes only its new host file's OpenCode entries
and follows the system-to-user packet in `docs/waits-system-preflight.md`;
the Authentik row is removed only through homelab-infra.

## Known effects to qualify

System mode converges waits only: it no longer re-renders the shared client,
quota, collector or the role's `mcp.json`, which stay as last converged, as on
the laptop. On omarchy-pc, `mcp_registrations_chaldea_waits_enabled: true`
registers `chaldea mcp --config ~/.config/chaldea/waits.json` from the
current client. System mode re-renders that file with the system socket
`/run/chaldea-waits-1000/waits.sock` and a `sessionPolicy` key, so the
interactive Chaldea MCP on omarchy-pc reads a changed file. Root qualifies
that consumer before omarchy-pc moves. This change does not touch MCP
registration.

Broader denied dispatch, including injected T3 tools, and real in-flight
renewal or reconnect remain unqualified, as on the laptop.
