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

## First release and activation

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

Antigravity CLI also receives a stdio Chaldea registration where
mcp_registrations_chaldea_providers allows it; see [Antigravity](antigravity.md)
for CLI/T3 isolation and the T3 enablement dependency.

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

`chaldea_job_client_exec_entry` and `chaldea_job_client_exec_node` remain
available for a separately admitted exec client. Set both or neither, as distinct
absolute paths containing only letters, digits, `.`, `_`, `-` and `/`, with
no `.` or `..` segment. Both launcher roles validate this before writing.
A selected entry must be a regular file and its Node an executable regular file;
missing selections exit 69 without fallback. Admission, rather than the launcher,
verifies the selected bytes. Keep a private selection under an owner-only directory.

### omarchy-pc admission to client-v0.4.36

omarchy-pc now leaves both overrides empty. All commands, including exec, use
`~/.local/share/chaldea/current/bin/chaldea` with the inventory-pinned Node.
The shared pin is client-v0.4.36, containing Chaldea PR121's concurrent exec
transport fix and retained refusal reasons. No separate private copy is needed:
the checksum-verified release directory is already owner-only, mode 0700.
This removes the old private controller selection without moving state or config.

The former selection remains on disk for recovery:

```text
/home/igor/.local/lib/chaldea-blob-controller/4f57cc27fa5a08da15233b018cf773c08a07291f/client-1e86175cd2ef2e11fdf4584d22cc73127a162d42/bin/chaldea
/home/igor/.local/lib/chaldea-blob-controller/4f57cc27fa5a08da15233b018cf773c08a07291f/node-26.10.0
```

Comparison against those installed bytes on 2026-11-23 found identical
`src/exec/blob.ts`, `custody.ts`, `artifacts.ts`, `state.ts`, `logs.ts`,
and `src/config/exec.ts`. Journal runtime pruning is identical; its changes
add a refusal field and sanitizer. History changes only add refusal reasons
to list/show. The exec client keeps the same custody calls and adds refusal
recording plus transport shutdown fixes. Pending records still bypass pruning,
their publication drafts remain, and artifact cleanup protects pending custody.

Compatibility job `0cb497a6-7e36-495f-833c-f957b03f9b01` passed on agent-a.
It used copied real journals in an asserted scratch HOME, with all filesystem
paths relocated there. Both old and new code retained all 715 pending records
byte-for-byte after relocation, including reserve metadata, after forced
zero-age/zero-count pruning, artifact cleanup and list/show. Artifact and
publication sentinel files survived. These sentinels exercise retention without
copying actual output or credentials. The real publication directory was empty.
The copied nonsecret blob config remained manual with the same store identity.
No logs, artifact payloads or publisher credentials were copied.

HOME and XDG remain unchanged by the launcher. The existing default journal,
publication directory, local artifact reserves, exec-hosts and SSH config stay
in place. There was no `exec.json` override at admission. Preserve any later
custom stateDir when qualifying another client. Keep the existing mode-0600
`~/.config/chaldea/blob.json` unchanged. The client reads it for artifact jobs;
manual publication records pending custody and makes no store request.
Publication still requires an operator, admitted tunnel and approved window.
This switch authorizes no upload, credential change or wider NAS access.

### Activation

Merging activates the launcher change through omarchy-pc's existing pull timer.
Before merging, verify that current resolves to the admitted client-v0.4.36,
its checksum-verified release and pinned Node are intact, and keep a copy of
the current launcher outside the repository. Do not recreate or remove blob.json.
After merging, record the exact merge commit and run from a checkout whose
`git rev-parse HEAD` equals it. Review the launcher-only check/diff before apply:

```sh
ansible-playbook -i inventory site.yml --limit omarchy-pc --tags chaldea_exec_launcher --check --diff
ansible-playbook -i inventory site.yml --limit omarchy-pc --tags chaldea_exec_launcher
```

This tag validates and renders only the launcher. It does not install a client,
move current, enroll SSH or restart services. Verify the resulting exec path,
existing jobs and pending custody with exec list/show, concurrent exec completion
and a busy refusal reason. Preserve the old controller and saved launcher.

### Rollback with custody intact

Restoring the former blob-capable controller is custody-compatible with this
admission, but restores its known exec bugs. Restore both exact override paths
in a reviewed inventory change and apply the same launcher-only tag. Keep
blob.json, journals, drafts, logs and local artifacts untouched. A saved launcher
is only temporary because the next pull renders inventory again.

An older ordinary client such as client-v0.4.11 is unsafe with pending custody:
its pruning deletes pending records, drafts and local artifact reserves.
Clearing the overrides is safe here only because current is admitted v0.4.36.
Before selecting any different rollback target, compare its retention paths and
repeat copied-state checks. If compatibility is unproven, stop exec activity
and take a bounded inventory of the effective state directory while no exec runs.
Every journal entry must be a regular nonsymlink file containing a JSON object,
with every blob state confirmed; every publication entry must belong to a
confirmed journal record. Pending, malformed, unreadable or incomplete state
refuses an incompatible rollback. Keep the compatible client, blob.json and
all state until an operator confirms publication. Closing the tunnel or window
pauses publication without discarding custody.

## Tests

`tests/test_chaldea_client.py` exercises the real role under a scratch HOME with a fake systemctl, including migration, repeat convergence, release validation, secret refusal and state preservation. Run checks through Chaldea with disk-backed scratch using `tools/ci.sh`.
