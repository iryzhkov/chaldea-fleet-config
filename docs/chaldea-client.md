# Fleet-managed Chaldea client

The `chaldea_client` role installs a checksum-pinned Node client without Git or npm on the destination. The app lives at `~/.local/share/chaldea/releases/client-vX.Y.Z`. The launcher, Chaldea MCP registration and user services use the stable `current` link. `previous` retains the previously active release; older versioned release directories and their cached archives/manifests are removed only after service convergence succeeds.

The client release is separate from the host release. The host tarball has bundled host entry points and cannot run the client CLI. Client releases contain `bin`, `src`, vendored T3 contracts, the exec protocol definition and locked production dependencies. They need the inventory-pinned Node runtime, currently 26.10.0. No compiler or npm install runs during convergence.

## First release and activation

This change does not publish a release or change any host. Inventory leaves `chaldea_client_enabled: false` and the version/checksum empty until a real artifact exists. That preserves the existing checkout launcher and MCP registration during bootstrap.

1. Merge the Chaldea client artifact PR into main. From an updated main checkout, tag the merged commit `client-v0.1.0` and push that tag. The client workflow accepts only `client-vX.Y.Z` tags whose commit is reachable from main. It installs production dependencies with scripts disabled, builds twice, compares both tarballs and manifests, verifies every archived file and smoke-tests extracted entry points before publishing.
2. Fetch `manifest.json` and `chaldea-client.tar.gz` from that GitHub release. Verify the tarball SHA-256 equals the manifest. Record `chaldea_client_version` and `chaldea_client_sha256` in `inventory/group_vars/all/main.yml`, and set `chaldea_client_enabled: true` in the same reviewed inventory change.
3. Verify the host-specific settings below, then merge the inventory pin. Later updates need only a new version/checksum merge and the same short converge.

The app manifest names the version, tarball SHA-256 and SHA-256 of every payload file. The role checks the pinned archive hash, matching manifest, exact member list and every file hash before extraction. It rejects links, special files, duplicate members, path traversal and missing CLI entry points. Extraction stages under the release directory and renames the completed release into place. Existing version directories are immutable; unexpected file drift fails with a message for inspection.

## Host settings and secrets

Inventory enables quota and waits on omarchy-pc. The laptop gets the client with both units disabled. Other agent hosts default to both units disabled. Disabled units are installed, stopped and disabled; they require no credentials.

The enabled units require these operator-provisioned files:

| Unit | Required secret paths |
| --- | --- |
| `chaldea-quota.service` | `~/.config/chaldea/t3-token` |
| `chaldea-waits.service` | `~/.config/chaldea/waits-t3-token`, `~/.config/chaldea/waits-answer-token` |

Before changing files, the role checks each enabled unit's required secrets with `stat`, without reading contents or calculating checksums. Each must be a nonempty regular file, not a symlink, owned by the converging user and mode 0600. Missing or unsafe credentials refuse the entire role before download, migration or service calls, naming the unit and required path. The role never provisions, prints, changes ownership or repairs permissions on tokens. The applications check credentials again when they open them.

`waits.json` is rendered from inventory. omarchy-pc retains its existing environment ID, LAN listen address, answer URL and token paths. The socket uses the host's actual user UID. The role backs up an existing waits config before replacing it and preserves unrelated files.

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
agents use the shared CLAUDE.md model roles, preserving cross-provider reviews.

Claude and Codex registrations, and only OpenCode's `mcp.chaldea` entry in
`~/.config/opencode/opencode.json`, point at the managed client on every enabled
host. Other OpenCode settings and servers are preserved. Symlinked configs,
JSONC peers and invalid JSON refuse rather than replacing an ambiguous source.
On hosts without waits, private `~/.config/chaldea/mcp.json` supplies the socket and
an inert environment label required by the MCP entry point. It starts no service.
Wait/decision calls still need the local waits service; `chaldea_route` runs in the
stdio process. Harnesses start that process on demand, with no T3 restart here.

Merging fleet main is deployment: the existing pull timers apply within four
hours on awake hosts; the laptop catches up on wake. Expected changes by host:

| Host | Changes |
| --- | --- |
| omarchy-pc | Client v0.2.0 to v0.3.0, current/previous links and managed cache retention; new route.json/capacity.json; restart existing enabled chaldea-quota and chaldea-waits units; refresh Chaldea registrations for Claude/Codex and add OpenCode registration. |
| agent-a | Same client bump and retention; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota and waits remain stopped and disabled. |
| agent-b | Same client bump and retention; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota and waits remain stopped and disabled. |
| laptop | Same client bump and retention on wake; new route.json/capacity.json/mcp.json; add Chaldea registration for Claude/Codex/OpenCode; quota and waits remain stopped and disabled. |

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

Check `systemctl --user status chaldea-quota.service chaldea-waits.service`, their journals, `readlink ~/.local/share/chaldea/current`, `chaldea quota status --json`, and the MCP registration. Confirm the waits database and quota observer state survived. Verify balance collection against the explicit runtime-home binding. Report each host separately as converged and verified.

For later rollback, pin the retained prior version and its published checksum in inventory and converge again. The prior current becomes `previous`. Services must start successfully before old releases are pruned. If a service fails, inspect its journal and re-converge with the prior pin; the role leaves the old release and legacy checkout available.

## Tests

`tests/test_chaldea_client.py` applies the real role under an asserted scratch HOME with a fake systemctl. It covers apply, repeat apply and check-mode idempotence, interrupted reload recovery, preflight before unit replacement, enabled services, missing/unsafe secret refusal, legacy checkout migration, preservation of config/state, rendered `%h` units, release retention, checksum/manifest/path/link refusal and disabled services without credentials. It never opens the live tokens or user manager.

Run tests through Chaldea with `TMPDIR` and `HOME` set to disk-backed job scratch. The existing `tools/ci.sh` runs these tests alongside the fleet checks, and activates a synthetic client during full-site double convergence to catch shared-directory permission conflicts.
