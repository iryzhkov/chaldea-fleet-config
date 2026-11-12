# Fleet-managed Chaldea client

The `chaldea_client` role installs a checksum-pinned Node client without Git or npm on the destination. The app lives at `~/.local/share/chaldea/releases/client-vX.Y.Z`. The launcher, Chaldea MCP registration and user services use the stable `current` link. `previous` retains the previously active release; older versioned release directories and their cached archives/manifests are removed only after service convergence succeeds. `chaldea_client_retained_versions` keeps at most six unique exact rollback versions that already exist; it never installs or selects one.

The client release is separate from the host release. The host tarball has bundled host entry points and cannot run the client CLI. Client releases contain `bin`, `src`, vendored T3 contracts, the exec protocol definition and locked production dependencies. They need the inventory-pinned Node runtime, currently 26.10.0. No compiler or npm install runs during convergence.

## Current client pin and operator exceptions

The desired ordinary-client release is `client-v0.4.23` from Chaldea source
`2a9aec02d003969af1a1fa19e995a4934288c75b`, PR99 merge `354206a`.
[Release workflow 40964375069](https://github.com/iryzhkov/chaldea/actions/runs/40964375069)
succeeded. The archive SHA-256 is
`b96c928d050d81e7be96841baf8ce0204927cd14fbd43b62cc0d4ac058fb9c82`;
the manifest SHA-256 is
`443cdf3598fb146e03ff1010bda6753ff1780d78a5d860182eedf185ac89b41a`.
The operator qualified agent-b on T3 0.1.5 with this client: current and streaming
quota were fresh, CHECK/REAL/repeat reported 2/10/0 changes and zero errors,
43 protected files were unchanged, and all 3211 manifest files verified.
The shared desired pin and matching PC override prevent ordinary pulls from
restoring an older client. The PC's FATE policy is unchanged.

## Laptop routing client selection

The laptop sets `chaldea_client_route_entry` to the already-installed immutable
`releases/client-v0.4.23/bin/chaldea`. The launcher reuses its command selector
pattern for `chaldea route`; routing-only MCP selects the same entry directly.
Both retain the ordinary inventory-pinned Node. Other commands keep their existing selection.
An unset or empty override preserves the old defaults.

This fixes the older client's rejection of T3 0.1.5 catalog keybindings.
It installs no payload and changes no links, services, route policy or credentials.
The parent operator owns live repair and verification. Missing selected entries
refuse rather than falling back to `current`. ## First release and activation

The following bootstrap procedure predates the current pin. Initially inventory
left `chaldea_client_enabled: false` and the version/checksum empty until a real
artifact existed, preserving the checkout launcher and MCP registration.

1. Merge the Chaldea client artifact PR into main. From an updated main checkout, tag the merged commit `client-v0.1.0` and push that tag. The client workflow accepts only `client-vX.Y.Z` tags whose commit is reachable from main. It installs production dependencies with scripts disabled, builds twice, compares both tarballs and manifests, verifies every archived file and smoke-tests extracted entry points before publishing.
2. Fetch `manifest.json` and `chaldea-client.tar.gz` from that GitHub release. Verify the tarball SHA-256 equals the manifest. Record `chaldea_client_version` and `chaldea_client_sha256` in `inventory/group_vars/all/main.yml`, and set `chaldea_client_enabled: true` in the same reviewed inventory change.
3. Verify the host-specific settings below, then merge the inventory pin. Later updates need only a new version/checksum merge and the same short converge.

The app manifest names the version, tarball SHA-256 and SHA-256 of every payload file. The role checks the pinned archive hash, matching manifest, exact member list and every file hash before extraction. It rejects links, special files, duplicate members, path traversal and missing CLI entry points. Extraction stages under the release directory and renames the completed release into place. Existing version directories are immutable; unexpected file drift fails with a message for inspection.

## Host settings and secrets

Inventory enables quota on the agent hosts. Disabled quota units require no credentials.

The enabled units require these operator-provisioned files:

| Unit | Required secret paths |
| --- | --- |
| `chaldea-quota.service` | `~/.config/chaldea/t3-token` |

Before changing files, the role checks each enabled unit's required secrets with `stat`, without reading contents or calculating checksums. Each must be a nonempty regular file, not a symlink, owned by the converging user and mode 0600. Missing or unsafe credentials refuse the entire role before download, migration or service calls, naming the unit and required path. The role never provisions, prints, changes ownership or repairs permissions on tokens. The applications check credentials again when they open them.

`quota.json` binds provider aliases to an explicit HOME, CODEX_HOME and installed Codex executable. Inventory binds `codex` to `{{ fleet_home }}/.codex` on omarchy-pc and the laptop. omarchy-pc's existing T3 provider configuration has no home/shadow override and its Codex HOME is `/home/igor/.codex`. Before enabling quota on another host, confirm T3's published `runtimePaths.shadowHomePath ?? runtimePaths.homePath` and set `chaldea_client_codex_home` to that exact effective home. If a custom home is configured, update this inventory binding with it. The collector needs the binding described in [Chaldea's cached headroom and credits contract](https://github.com/iryzhkov/chaldea/blob/main/docs/quota.md#cached-headroom-and-credits), including authenticated ChatGPT auth and a loopback T3 URL. An unmatched context reports unknown balance; it never borrows the invoking shell's credentials. The Codex executable defaults to the fleet's mise shim.

## Advisory routing rollout

The client-v0.3.0 pin comes from Chaldea main `181838f`. The reviewed archive
SHA-256 is `38815b50ae8efbd9379f707af3fe8265a18e1fedd7814c2644ec73c91a8f5fa1`.
The role writes private `~/.config/chaldea/route.json` and `capacity.json` on every
enabled client host. Defaults match [the pinned routing contract](https://github.com/iryzhkov/chaldea/blob/181838f/docs/route.md):
10% pacing margin and tight threshold, 10-point failure margin, 100 minimum turns,
15-minute quota freshness, three-day analytics freshness, 2x heavy projection,
24-hour burn window and expiry horizon, 5% reserve and 72-hour Codex reset lead.
No credit conversion, expiry or Claude refill inventory is asserted without
operator measurements. `chaldea_client_capacity_providers` leaves room for them.

The pinned client fixes the role pairs: builder is Opus 5.5/Sol 6.1 high,
critical-review is Fable 5.1/Astra medium, bulk-read is Sonnet 5.5/Luna 6 medium,
and general is Opus 5.5/Sol 6.1 medium. Haiku and OpenCode are excluded as routing
candidates. The client fixes the Slopalytics URL to
https://slopalytics.com/data/t3-usage.json. Neither role pairs nor the URL are valid
JSON configuration keys. Preserve them by pinning the reviewed client.

`chaldea_client_claude_usage_enabled: false` is explicit inventory policy on all
four hosts. Igor has not approved the optional collector. Any future opt-in needs
his approval and verified local account binding; this rollout never reads Claude
credentials. Route recommendations need an existing local T3 token with
`orchestration:read`, defaulting to `~/.config/chaldea/t3-token`; the role never
creates one. Missing tokens/catalogs produce an unavailable recommendation and
agents use the shared CLAUDE.md model roles and `review-delegation`'s provider rule
and "Quota exception". An unavailable recommendation alone grants no waiver.

Claude and Codex registrations, and only OpenCode's `mcp.chaldea` entry in
`~/.config/opencode/opencode.json`, point at the managed client on every enabled
host. Other OpenCode settings and servers are preserved. Symlinked configs,
JSONC peers and invalid JSON refuse rather than replacing an ambiguous source.
Private `~/.config/chaldea/mcp.json` supplies the routing MCP configuration.
`chaldea_route` runs in the stdio process. Harnesses start that process on demand, with no T3 restart here.

Merging fleet main is deployment: the existing pull timers apply within four
hours on awake hosts; the laptop catches up on wake. Expected changes by host:

| Host | Changes |
| --- | --- |
| agent-a | Same client bump and retention; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota remains stopped and disabled. |
| agent-b | Same client bump and retention; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota remains stopped and disabled. |
| laptop | Same client bump and retention on wake; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota remains stopped and disabled. |

All four also receive the shared route-before-delegation CLAUDE.md, AGENTS.md and
Chaldea/review-delegation/roadmap-executor skill updates through `agent_config`.
Fleet owns these deployed sources. Omarchy-setup retains bootstrap CLAUDE.md and
AGENTS generator sources; synchronize the short routing rule there without running
its generator over fleet-owned files. The skills named above have no second source
in omarchy-setup. No new daemon, timer, collector or service enablement is added;
job host binaries and host-v0.2.1 remain unchanged by this client rollout.
No manual host convergence is part of the PR work.

## Migration and converge

Run on each authorized host individually, limited to its own inventory entry:

```sh
ansible-playbook -i inventory site.yml --limit omarchy-pc \
  --tags chaldea_client,mcp_registrations --check --diff
ansible-playbook -i inventory site.yml --limit omarchy-pc \
  --tags chaldea_client,mcp_registrations
```

Use `--limit laptop` on the laptop. A fresh check run explains that download and extraction are deferred. Once cached, check mode verifies the artifact without mutation. A second real converge changes nothing.

The role writes managed units to the same filenames as the hand-made units, using Ansible's atomic file replacement. It keeps backups of replaced units, so there is no interval in which the old files have been deleted and the managed files are absent. Unit paths use systemd `%h`; no home directory is hard-coded. The role reloads the user manager on every converge, and restarts enabled services when the release, units or configuration change. It writes a restart marker before changing definitions and clears it only after verifying enabled services are active with the managed ExecStart loaded. An interrupted apply therefore retries the reload and restart on the next run, even when the files already match. It starts stopped enabled units on an otherwise unchanged converge.

The role updates its Chaldea MCP registration before retiring the checkout, so a later failure in another registration cannot strand the old command path. After services converge successfully, the role detects `app/.git` and renames the old `app` checkout to `app.pre-fleet`. It never removes that backup. If both paths exist, it refuses to overwrite either. `~/.local/state/chaldea` and existing configuration contents outside the rendered config files are preserved. Unit/config backups and `app.pre-fleet` let an operator restore the old installation if the first migration needs rollback.


For later rollback, pin the retained prior version and its published checksum in inventory and converge again. The prior current becomes `previous`. Services must start successfully before old releases are pruned. If a service fails, inspect its journal and re-converge with the prior pin; the role leaves the old release and legacy checkout available.

## Exec-only client selection

`chaldea_job_client_exec_entry` and `chaldea_job_client_exec_node` let
`chaldea exec` on one host run a separately admitted client, such as the
blob-capable private controller, while every other command keeps the pinned
release, its services and its `current` link. Both default to empty, which
renders the launcher byte for byte as before; only omarchy-pc sets them. Set both or neither, as distinct absolute paths of letters, digits, `.`,
`_`, `-` and `/` with no `.` or `..` segment. Both roles that render
`~/.local/bin/chaldea` refuse anything else before they change a file.

The launcher checks only the first argument. When it is exactly `exec`, the
launcher runs the selected Node on the selected entry with the arguments, exit
status, environment and working directory unchanged. HOME and XDG are not
touched, so the exec journal, state, `exec-hosts`, SSH configuration and
`--host` fallback stay where the pinned client keeps them. Every other
invocation, including no arguments, `--describe`, `--help`, `wait`,
`decision`, `quota`, `route` and `artifacts`, still runs the pinned release.
A selected entry that is not a regular file, or a Node that is not an executable
regular file, makes `chaldea exec` exit 69 without falling back. The launcher
does not hash the selected bytes: deployment admission establishes them, so keep
both under an owner-only directory.

A `blob.json` alone cannot add custody to ordinary exec: client-v0.4.11 has no
blob support and ignores the file. The selected client reads the default
`$XDG_CONFIG_HOME/chaldea/blob.json` only when `--artifact` names an output;
without one, a job behaves as before. With `"publication": "manual"`, an
artifact job records a pending custody intent that keeps its journal record and
local artifact reserve until publication is confirmed, and makes no network
attempt to the store, whether or not the tunnel is open. Publication still
needs an operator, an admitted tunnel and an approved window. Enabling manual
mode uploads nothing and widens no NAS artifact-risk approval. Journal
retention is unchanged except that pending custody records are kept.

omarchy-pc sets both in `inventory/hosts.yml`:

```yaml
chaldea_job_client_exec_entry: /home/igor/.local/lib/chaldea-blob-controller/4f57cc27fa5a08da15233b018cf773c08a07291f/client-1e86175cd2ef2e11fdf4584d22cc73127a162d42/bin/chaldea
chaldea_job_client_exec_node: /home/igor/.local/lib/chaldea-blob-controller/4f57cc27fa5a08da15233b018cf773c08a07291f/node-26.10.0
```

The matching manual `~/.config/chaldea/blob.json`, mode 0600, names the
existing publisher credential by path and contains no secret:

```json
{"version": 1, "endpoint": "http://127.0.0.1:43900", "bucket": "artifacts-igor-exec",
 "principal": "igor-exec", "region": "garage", "publication": "manual",
 "credentialFile": "/home/igor/.local/share/chaldea-blob-profiles/publisher/credential.json"}
```

**Merging the enrollment activates it on omarchy-pc.** That host's pull timer
converges main with the full site play, and both launcher roles render the same
bytes, so the next pull after the merge installs the selection. Before the
merge, the operator verifies the admitted bytes of the selected Node and entry
and the custody of the publisher credential, confirms that the normal
`blob.json` and `exec.json` are absent, keeps a copy of the current launcher,
and creates `blob.json` exclusively, never over an existing file. Without
`blob.json`, the selected client runs `--artifact` jobs without custody, as
before. After the merge, record the exact merge commit, and converge only the
launcher at once rather than waiting for the timer. Run from a checkout whose
`git rev-parse HEAD` equals that recorded commit, not a moving `main`, and
review the check run's diff first:

```sh
ansible-playbook -i inventory site.yml --limit omarchy-pc --tags chaldea_exec_launcher --check --diff
ansible-playbook -i inventory site.yml --limit omarchy-pc --tags chaldea_exec_launcher
```

The tag runs the validation and the launcher template only: no SSH enrollment,
client release, `current` link or user service.

### Rollback only without pending custody

Rolling back hands real `chaldea exec` to client-v0.4.11, which knows nothing
of pending custody: its journal pruning deletes pending records together with
their publication drafts and local artifact reserves. Before any step that lets
client-v0.4.11 run `chaldea exec` again (removing either setting on main,
rendering or restoring an earlier launcher) and before removing `blob.json`,
even before the merge, take a bounded read-only inventory of the exec state
directory (`$XDG_STATE_HOME/chaldea/exec` unless `exec.json` sets `stateDir`)
while no `chaldea exec` runs, and start none until the rollback completes:

- every entry in `journal/` is a regular file (not a symlink) holding a JSON
  object, and no record has a `blob` field whose `state` is anything other than
  `confirmed`;
- every entry under `publication/` is named for a job whose journal record has
  `blob.state` `confirmed`.

If any record is pending, or any entry is malformed, unreadable, unsafe or
otherwise incomplete, refuse the rollback. Keep the selection, `blob.json`,
local artifacts, journals and reserves, and do not abandon, delete or retry
anything until an operator has confirmed publication. To pause publication,
close the tunnel or the publication window and keep the selected client; that
is not a rollback. Only when the inventory is clean, remove both settings on
main (a source change under the same review and merge rules) and run the same
launcher-only command; the launcher returns to the pinned bytes. Restoring a
saved launcher by hand lasts only until the next pull while the settings remain
on main.

## Tests

`tests/test_chaldea_client.py` exercises the real role under a scratch HOME with a fake systemctl, including migration, repeat convergence, release validation, secret refusal and state preservation. Run checks through Chaldea with disk-backed scratch using `tools/ci.sh`.
