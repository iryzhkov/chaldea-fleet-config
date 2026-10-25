# System waits namespace qualification

This opt-in runs the existing waits daemon as the existing fleet UID/GID under
the system manager. Set `chaldea_client_waits_service_mode: system` and
`chaldea_client_waits_enabled: true` only in a separately reviewed host packet.
Default user mode and waits-off clients keep their existing configuration.
Protected sessions in user mode refuse before any mutation.

System mode converges waits only. It reuses the already installed
`~/.local/share/chaldea/current` client and Node runtime by default. An explicit
`chaldea_client_waits_runtime_root` may select an already staged canary runtime.
The runtime, its entrypoints and their ancestry must exist and be safe, and the
resolved runtime must remain inside the resolved existing Chaldea root. A normal
current symlink is allowed within that root. The daemon and maintained loader use
the measured canonical runtime, also recorded by the preflight. It never installs a
release, changes current/previous, or converges quota, T3, collector or helper.
The normal role dispatches system mode to the same role-only
`tasks_from: waits-system` entrypoint. Initial setup must reuse homelab-infra
for Authentik accounts, enrollment and private delivery. This role owns the
waits service, protected profiles and preflight.

The system unit and the credential-free oneshot include the same sandbox.
They set explicit HOME and paths, keep WakeStore at
`HOME/.local/state/chaldea/waits.sqlite`, and retain home-based log, T3 and auth
pointers. Only that state directory and the private 0700
`/run/chaldea-waits-UID` runtime directory are writable. The socket moves into
that runtime directory. Clients must use the role-rendered waits.json.
RuntimeDirectoryPreserve retains the runtime while a preflight runs alongside
an existing daemon. No broad /run write exception is granted.

[systemd 257 PrivateUsers](https://www.freedesktop.org/software/systemd/man/257/systemd.exec.html#PrivateUsers=)
documents that true/self maps root and the service UID/GID in the system
manager. Per-user managers omit root. Identity mapping would expose all 65536
identities, which this design does not need. Runtime support is unqualified
until the actual host probe succeeds. Render and mocked namespace tests cannot
prove kernel mappings or mount restrictions.

## Next operator packet, not authorization

Prepare one host packet containing the exact fleet commit, host and hostname,
fleet UID/GID/home, Node path/version, installed current client commit,
proposed rendered unit/checker digests, current user/system unit definitions
and drop-ins, active states, socket and database ownership, and rollback files.
Record the selected waits runtime path and its measured canonical path, and why
that installed client exports src/session/policy.ts loadSessionPolicy.
Do not change release pins to run this packet.

1. With no SOPS, enrollment, app password delivery or provider work, run
   `playbooks/chaldea-waits-preflight.yml` on exactly the approved host using
   the normal inventory, an explicit limit and the two opt-in variables.
   This invokes only `chaldea_client/tasks/waits-preflight.yml`.
2. Retain Ansible output, the probe unit and systemd version, its journal JSON
   containing actual UID/GID maps and ancestor UID/GID/modes, and system-manager
   sandbox properties. Require exactly UID0 plus fleet UID and GID0 plus fleet
   GID identity mappings. The public directory chain must be root-owned without
   group/other writes. The checker reads only proc maps and those directories.
   It does not read private credentials, policy contents or waits.json, import
   the policy loader, load SOPS, call a network or dispatch a provider. The
   sandbox itself has the daemon's filesystem permissions; the checker is not
   a hostile-code isolation boundary.
3. Only after that evidence passes, use the existing homelab-infra enrollment
   and delivery workflow. Use the role-only waits-system entrypoint to render
   the public policy and activate waits. It reruns the namespace probe before
   credential inspection. Every daemon start reruns the namespace checker and,
   when policy is enabled, the maintained loadSessionPolicy with its default
   root-only ownership rules before the daemon opens private credentials.
4. Preserve backups and require a loaded managed system unit, active non-root
   owner, expected hardening, masked/inactive user unit and one database owner.
   No service-ready claim qualifies token acquisition, ACLs or provider launch.
   Any failure stops the packet before enrollment or further activation.

Ownership admission accepts only exact role-rendered existing units with their
expected owner and manager fragment path, without drop-ins. Missing units or
the previously masked user unit are allowed. Unknown states, foreign units,
aliases and two active owners fail. An unavailable user manager also fails.
The migration stops/disables only the verified role-owned user unit, backs it
up as chaldea-waits.service.pre-system, masks it and verifies inactivity before
system startup. It never runs both against the DB. Before changing any waits configuration,
checker, public policy or unit, check-mode prediction persists restart intent in
`HOME/.local/state/chaldea/waits-system-restart-required`. Interrupted runs retain
that intent and force a restart even when the next render matches. Restart or
readiness failure keeps it; only verified success clears it. A converged run
without pending intent does not restart again. Readiness also checks the loaded
ExecStart uses the measured runtime and expected config path. Exact definition admission
can refuse later configuration changes; review the old definition explicitly
instead of bypassing the refusal.

When the existing managed user unit names an older Node version, a reviewed
system-migration packet may set the protected
`chaldea_client_waits_legacy_user_node_version` to that exact numeric version,
for example `26.10.0` while `chaldea_node_version` remains `26.12.0`.
Empty preserves existing admission. The override requires system mode with waits
enabled and an existing inactive, disabled regular user unit. Exact rendered
bytes, owner, 0644 mode, single link, fragment path and absence of drop-ins remain
mandatory. An interrupted masked migration requires the exact same guarded
`chaldea-waits.service.pre-system` backup. Missing units, active/enabled legacy
owners and foreign backups are refused. The override only affects the two legacy
checksum comparisons. It never installs or executes the old Node version or
changes system units, runtime, deadline or policy. Retain it while that legacy
backup remains reserved. Retiring the backup needs a separately reviewed packet.

The persistent system unit names the canonical runtime it was rendered for, so
selecting a different `chaldea_client_waits_runtime_root` makes exact admission
refuse the installed unit before any write. A reviewed runtime-migration change
may set the protected `chaldea_client_waits_legacy_system_runtime` to the exact
old canonical runtime path, for example
`~/.local/share/chaldea/releases/client-v0.4.18` while the new root selects
`client-v0.4.20`. Empty preserves existing admission. The override requires
persistent system mode with waits enabled and no deadline, a normalized absolute
path inside the Chaldea root other than the selected runtime, and an existing
regular system unit. It adds only one checksum expectation: the role's exact
system rendering with that old runtime. Root ownership, 0644 mode, single link,
loaded fragment path, absence of drop-ins and the single-owner rule remain
mandatory, and drifted or foreign units are refused. The pull then installs the
current rendering (keeping the old bytes as its backup) and restarts waits
through the usual restart intent and readiness checks. The override never
selects, installs or runs the old runtime. Remove it in a separately reviewed
change once the installed unit is the current rendering.

Rollback needs a new concrete packet. Stop and disable the role-owned system
unit first, verify it is inactive, preserve its definition and waits.json
backup, then remove the system definition, restore the saved user definition
and old config/socket, reload managers and start only the user owner. Withdraw
protected sessions before returning to user mode. Default user convergence
refuses while the reserved system unit exists. Keep the SQLite DB and its WAL
and SHM together; no WakeStore conversion or DB copying is part of migration.
