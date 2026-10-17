# Fleet-managed Chaldea client

The `chaldea_client` role installs a checksum-pinned Node client without Git or npm on the destination. The app lives at `~/.local/share/chaldea/releases/client-vX.Y.Z`. The launcher, Chaldea MCP registration and user services use the stable `current` link. `previous` retains the previously active release; older versioned release directories are removed only after service convergence succeeds.

The client release is separate from the host release. The host tarball has bundled host entry points and cannot run the client CLI. Client releases contain `bin`, `src`, vendored T3 contracts, the exec protocol definition and locked production dependencies. They need the inventory-pinned Node runtime, currently 26.10.0. No compiler or npm install runs during convergence.

## First release and activation

This change does not publish a release or change any host. Inventory leaves `chaldea_client_enabled: false` and the version/checksum empty until a real artifact exists. That preserves the existing checkout launcher and MCP registration during bootstrap.

1. Merge the Chaldea client artifact PR into main. From an updated main checkout, tag the merged commit `client-v0.1.0` and push that tag. The client workflow accepts only `client-vX.Y.Z` tags whose commit is reachable from main. It installs production dependencies with scripts disabled, builds twice, compares both tarballs and manifests, verifies every archived file and smoke-tests extracted entry points before publishing.
2. Fetch `manifest.json` and `chaldea-client.tar.gz` from that GitHub release. Verify the tarball SHA-256 equals the manifest. Record `chaldea_client_version` and `chaldea_client_sha256` in `inventory/group_vars/all.yml`, and set `chaldea_client_enabled: true` in the same reviewed inventory change.
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

## Migration and converge

Run on each authorized host individually, limited to its own inventory entry:

```sh
ansible-playbook -i inventory site.yml --limit omarchy-pc \
  --tags chaldea_client,mcp_registrations --check --diff
ansible-playbook -i inventory site.yml --limit omarchy-pc \
  --tags chaldea_client,mcp_registrations
```

Use `--limit laptop` on the laptop. A fresh check run explains that download and extraction are deferred. Once cached, check mode verifies the artifact without mutation. A second real converge changes nothing.

The role writes managed units to the same filenames as the hand-made units, using Ansible's atomic file replacement. It keeps backups of replaced units, so there is no interval in which the old files have been deleted and the managed files are absent. Unit paths use systemd `%h`; no home directory is hard-coded. The role reloads the user manager and restarts enabled services when the release, units or configuration change. It starts stopped enabled units on an otherwise unchanged converge.

After services converge successfully, the role detects `app/.git` and renames the old `app` checkout to `app.pre-fleet`. It never removes that backup. If both paths exist, it refuses to overwrite either. `~/.local/state/chaldea` and existing configuration contents outside the rendered config files are preserved. Unit/config backups and `app.pre-fleet` let an operator restore the old installation if the first migration needs rollback.

Check `systemctl --user status chaldea-quota.service chaldea-waits.service`, their journals, `readlink ~/.local/share/chaldea/current`, `chaldea quota status --json`, and the MCP registration. Confirm the waits database and quota observer state survived. Verify balance collection against the explicit runtime-home binding. Report each host separately as converged and verified.

For later rollback, pin the retained prior version and its published checksum in inventory and converge again. The prior current becomes `previous`. Services must start successfully before old releases are pruned. If a service fails, inspect its journal and re-converge with the prior pin; the role leaves the old release and legacy checkout available.

## Tests

`tests/test_chaldea_client.py` applies the real role under an asserted scratch HOME with a fake systemctl. It covers apply, repeat apply and check-mode idempotence, enabled services, missing/unsafe secret refusal, legacy checkout migration, preservation of config/state, rendered `%h` units, release retention, checksum/manifest/path/link refusal and disabled services without credentials. It never opens the live tokens or user manager.

Run tests through Chaldea with `TMPDIR` and `HOME` set to disk-backed job scratch. The existing `tools/ci.sh` runs these tests alongside the fleet checks.
