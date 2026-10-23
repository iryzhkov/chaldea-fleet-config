# Fleet-managed Chaldea client

The `chaldea_client` role installs a checksum-pinned Node client without Git or npm on the destination. The app lives at `~/.local/share/chaldea/releases/client-vX.Y.Z`. The launcher, Chaldea MCP registration and user services use the stable `current` link. `previous` retains the previously active release; older versioned release directories and their cached archives/manifests are removed only after service convergence succeeds. `chaldea_client_retained_versions` keeps at most six unique exact rollback versions that already exist; it never installs or selects one.

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
agents use the shared CLAUDE.md model roles and `review-delegation`'s provider rule
and "Quota exception". An unavailable recommendation alone grants no waiver.

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

## Session policy

Protected sessions require the explicitly opted-in system waits mode. User mode
refuses this combination before writes because its namespace omits root. See
[system waits preflight](waits-system-preflight.md) for the role-only entrypoints,
pre-enrollment qualification and rollback packet. This source does not activate
or migrate any host.

Off on every host. `chaldea_client_session_policy_enabled: false` renders no
policy and leaves `waits.json` without a `sessionPolicy` key, byte for byte as
before. Inventory enables nothing here.

When enabled on a host with waits enabled, the role renders the protected
Chaldea session policy at the fixed path `/etc/chaldea/sessions/policy.json`
(role `vars/`, not settable from inventory) and adds
`"sessionPolicy": "/etc/chaldea/sessions/policy.json"` to `waits.json`. The
policy is public configuration read by the ordinary service user, so it is
root-owned, mode 0644 and a single link, and `/`, `/etc`, `/etc/chaldea` and
`/etc/chaldea/sessions` must be root-owned directories, not links and not
group- or other-writable. The role creates the last two as root (become) and
refuses any other layout before writing. It holds no credential.

Inventory supplies:

- `chaldea_client_session_ceilings`: one to eight operator ceilings;
- `chaldea_client_session_presets`: one to sixteen fixed presets, each with
  exactly the policy's preset fields and `delegate: false`;
- `chaldea_client_session_enrollments`: optional, keyed by preset ID. Each
  legacy Jocasta entry is exactly `{form: app_password, issuer, tokenUrl, jwksUrl, clientId,
  username, scope: jocasta.read, resource, project, maxTokenSeconds: 300,
  secretFile}`. The URLs must be canonical HTTPS (lower-case host, no default
  port, no userinfo, query or fragment), with the token and JWKS URLs on the
  issuer's origin. `project` must equal the preset's project, whose only
  Jocasta grant resource must be `project:<project>`. `secretFile` must be
  `~/.config/chaldea/authentik/<preset>.app-password`, the file
  homelab-infra's `authentik_machine_identities` role delivers. Without
  enrollments the policy has no `enrollments` key, so preset hashes stay the
  same.

Each `secretFile` is checked with `stat` only, like the unit tokens above: a
nonempty regular 0600 file owned by the converging user, not a link, in a
directory owned by that user with no group or other access. The role never
creates, reads, prints or repairs it. The client parses the policy again at
every start, and its rules are authoritative; this role refuses what it would
refuse, earlier and naming the inventory field. A policy with enrollments needs
a client release whose parser accepts `enrollments`; selecting that release is a
separate pin change. Disabling the policy later leaves an existing policy file
in place, inert because `waits.json` no longer names it.

The role-local `session_enrollment.py` filter validates public data before
stat or writes. Both normal activation and the credential-free public gate use
these checks through `tasks/session-policy-public-validate.yml`. Legacy Jocasta enrollment fields and rendered JSON stay unchanged.
New enrollments replace `project` with `audience` and the matching grant arrays.
Their preset must have exactly one service, equal to that flat grant, including
scope spelling and array order. The preset's `project` remains the local
authorization/accounting domain. New enrollments contain no Jocasta project.

| Audience | Fixed resource | Required flat fields |
| --- | --- | --- |
| `ov` | `https://ov.mcp.ryzhkov.dev/mcp` | `scope: ov.read`, `ov_namespaces` |
| `homelab` | `https://homelab.mcp.ryzhkov.dev/mcp` | `scope: homelab.read`, `homelab_services`, `homelab_hosts` |
| `ha` | `https://ha.mcp.ryzhkov.dev/mcp` | `scope`, `ha_entities`, `ha_actions` |
| `holonet` | `https://media.mcp.ryzhkov.dev/mcp` | holonet.read, one server/catalog user/library, empty history/target arrays, catalog.read, namespace |

HoloNet follows the shared catalog-only fixture and exact immutable ceiling.
No history/UserData/write grants are accepted. Changing server, user, library or
namespace is not narrowing. Operator inventory must identify TV and Movies;
no names or runtime credential reach are inferred. Existing protected-policy
metadata checks, public validation before secret stat, no-secret-open rendering
and actual-UID loading gates remain in force. This source adds no enrollment,
account, credential, deployment or live access authority.

OV needs 1..16 unique nonoverlapping canonical roots of at most 1024 ASCII
characters. Roots use `viking://resources/(segment/)*segment`; segments contain
only letters, digits or `_@+.,=-`, excluding dot segments. Escaping, wildcards,
empty segments and trailing slashes refuse. Each homelab list has 0..128 unique
IDs matching `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Explicit empty lists grant nothing.

HA needs 1..64 unique entities matching
`(light|switch|sensor|binary_sensor)[.][a-z0-9_]{1,96}`, each at most 112
characters, and 1..3 unique actions from `state.read`, `light.control` and
`switch.control`. Scope is exactly `ha.read`, `ha.control`,
`ha.read ha.control` or `ha.control ha.read`. State reads require `ha.read`;
control actions require `ha.control`. Initial approved presets remain
`ha.read` with `state.read`. Control requires explicit protected operator
grants and live registry/control qualification. This validator cannot establish
that qualification.

Every new enrollment has exactly the common fields `form: app_password`,
`issuer`, `tokenUrl`, `jwksUrl`, `clientId`, `username`, `resource`,
`maxTokenSeconds: 300`, `secretFile`, plus its flat service fields above.
Missing/null arrays, duplicates, extra keys and arbitrary claims refuse.
Canonical provider URLs have no escaping, dot or empty path segments. Issuer
ends in `/`; JWKS equals issuer plus `jwks/`; token URL equals the issuer
origin plus `/application/o/token/`. Secret paths retain the exact per-preset
path above. New presets cannot reuse a secret file or ordinary account at one
Authentik origin. Different services at that origin need distinct issuers and
client IDs; presets of one service may share a provider.

New grants must fit one whole ceiling with matching local project, sufficient
duration and allowed destinations. OV uses equal/ancestor roots at slash
boundaries, homelab uses both list subsets, and HA uses entity/action/scope
subsets. Ceilings never merge. Legacy `{audience, grants}` entries remain
parse-only for other services, including in ceilings, and cannot authorize a
new flat enrollment. The validator leaves declaration order intact.

The rendered UTF-8 policy must fit 64 KiB before any stat or write. Maximal
individual arrays can still exceed this whole-file bound. The existing
actual-user policy-load preflight remains authoritative before activation.
No service manager, native HTTP MCP binding, provider, account or release pin
is installed by this validation change. Deployment requires a compatible
Chaldea release and separate live helper/endpoint qualification.

## Fixed provider profiles

A fixed provider profile is the limited launch context of a Chaldea-launched
session. Interactive T3 threads keep the operator's ordinary provider settings;
only the T3 provider instance that a protected preset names points at a profile
launcher. The profile adds no runner, service, lifecycle or provider fork: the
stock T3 server starts the stock Codex binary through one rendered launcher.

Off on every host. `chaldea_client_session_profiles: {}` renders nothing. The
role delivers profiles from `waits-system.yml`, right after the protected policy,
so they require `chaldea_client_session_policy_enabled: true` in system waits
mode. Public validation runs with the other waits checks before any mutation.
Only the `codex` driver is supported.

Each profile is keyed by a name matching `[a-z0-9][a-z0-9-]{0,47}` and has
exactly these fields; every one is an operator input:

```yaml
chaldea_client_session_profiles:
  codex-tooling-reporter:                 # files under /etc/chaldea/sessions/<name>/
    driver: codex
    native:                               # already-installed official Codex binary
      source: /home/igor/.local/share/mise/installs/codex/0.163.0/bin/codex
      sha256: 8a96f66d059d653e68bfd5f3c79337e6f1d7d170d80bf705eb7d0249b34c0ece
      size: 257816200
    host:                                 # its matching official companion
      source: /home/igor/.local/share/mise/installs/codex/0.163.0/bin/codex-code-mode-host
      sha256: 255eccc8a5c1d267dc0acbc815cc83aaa1f50955bd99943b29f00cafcdcab771
      size: 67118080
    catalog:                              # public one-model catalog, apply_patch null
      source: /home/igor/.config/chaldea/profile-inputs/codex-tooling-models.json
      sha256: "<sha256 of the reviewed catalog file>"
      size: 65174
    elf_machine: 183                      # 183 AArch64, 62 x86-64
    model: gpt-6.1-sol                    # must equal the preset model
    home: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/home
    tmpdir: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/tmp
    cwd: /home/igor                       # the T3 server's working directory
    preset: tooling-reporter              # a declared preset with an enrollment
    audience: jocasta
    server: jocasta_tooling
    url: https://jocasta.mcp.ryzhkov.dev/mcp   # must equal the enrollment resource
    tools: [get, history, list, search]   # subset of the preset's granted actions
    disabled_servers: [jocasta, home_only]   # operator MCP servers to neutralize
```

The values above are illustrations; the preset name, project and paths are
chosen per deployment. Hashes and sizes are reviewed literal inputs. The role
never infers them from a target, downloads a binary or changes a version: it
refuses unless each source is a regular file, not a link, writable by no one
else, with exactly the pinned size and SHA-256. The catalog must hold exactly
the profile model with `apply_patch_tool_type` explicitly `null`, at most 64 KiB.
Derive it from the pinned Codex source `codex-rs/models-manager/models.json`,
changing only that field.

`home` and `tmpdir` lie inside the fleet home and `home` differs from it, so the
operator's own `~/.codex` is never touched. The operator provisions both
directories and the profile's independent Codex login before enabling the
profile: `home` is owned by the fleet user with mode 0700, `home/.codex` exists
and is writable only by its owner. The role checks these with `stat` only. It
never lists, creates, copies, reads or removes anything in the home except the
one file below.

The role writes, as root and with no group or other write access:

| Path | Content |
| --- | --- |
| `/etc/chaldea/sessions/<name>/codex` | native binary, byte for byte, 0755 |
| `/etc/chaldea/sessions/<name>/codex-code-mode-host` | companion, 0755 |
| `/etc/chaldea/sessions/<name>/models.json` | catalog, 0644 |
| `/etc/chaldea/sessions/<name>/mcp.json` | public MCP description, 0644 |
| `<home>/.codex/config.toml` | native profile config, 0644 |
| `/etc/chaldea/sessions/<name>/exec` | launcher, 0755, written last |

The headers helper is the resolved system waits runtime's
`bin/chaldea session headers --preset <preset> --audience <audience>
--config ~/.config/chaldea/waits.json`, run with the pinned Node. It is bound
to the runtime the waits service runs, not to the shared client `current`.
Before writing, every existing target must be a single-link regular file owned
by root and every existing protected directory root-owned; links and foreign
files refuse. After writing, each file must hold exactly its pinned or rendered
SHA-256. A second converge changes nothing.

The launcher embeds every expected path, hash, size, UID and the exact public
file hashes as literals. At each start it requires the fleet UID, the fixed
`cwd` and argv `app-server`; reads `mcp.json`, `config.toml` and the catalog
by directory descriptors without following links, checking root custody, mode,
size, SHA-256, stable metadata, complete JSON/TOML equality and the one-model
catalog; pins both ELFs by descriptor, size, hash and ELF machine; then
executes the held native descriptor with a fixed environment (`HOME`,
`CODEX_HOME`, `TMPDIR`, `PATH`). The stock config narrows Codex: no plugins,
apps, multi-agent, goals, image viewer, shell tool or web search, and
`--strict-config`. Any failure exits 78 with `CODEX_PROFILE_REFUSED`.

Enabling a profile for a session takes three operator steps outside this role:
provision the home and its login, create the T3 Codex provider instance with
`binaryPath: /etc/chaldea/sessions/<name>/exec` and `homePath: <home>/.codex`,
and name that instance in the preset. Order removal the other way round.

### Rollback

The guarded inverse removes a retired profile's role-owned files. First remove
the preset (or disable the session policy) and the T3 provider instance that
uses the launcher, so no session can start it. Then move the profile from
`chaldea_client_session_profiles` to:

```yaml
chaldea_client_session_profiles_absent:
  - name: codex-tooling-reporter
    home: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/home
```

A normal converge, or the role-only `session-profiles-absent.yml` entrypoint,
removes the launcher first, then the other four protected files and
`<home>/.codex/config.toml`, and finally the profile directory with `rmdir`.
It refuses links, non-root files and foreign directories before removing
anything, and stops if anything unknown remains in the profile directory. The
profile home, its login and the source binaries are left in place. A name
cannot be delivered and retired in the same run.

### Limits

The launcher and file custody prevent accidents and stale or edited inputs;
they are not containment of a hostile process running as the same UID. The
profile home and `home/.codex` belong to the fleet user, so that UID can race
the checks, replace `config.toml` between launches, or swap a directory while
the role writes or removes the one root-owned file there. Codex and its tools
also run as that UID. T3 injects its own control tools and request-level MCP
configuration into every session it starts; the profile cannot remove that
catalog, and limited sessions rely on the protected preset and the service's
own ACL rather than on tool absence. Renewal, restart recovery and multi-page
continuation keep their separately stated qualification limits.

## Bounded canary entrypoints

The role-only `session-policy-gate.yml` entrypoint validates and renders the public
policy, runs the namespace preflight, then calls the staged runtime's actual
`loadSessionPolicy` through `waits-policy-check.mjs` in the same system sandbox.
It imports the shared public validator and writer, never the credential task.
It refuses fixture owner/location overrides. A future enrollment pointer may
name a password that does not exist yet. No password/control-token metadata is
inspected, SOPS loaded, network called, waits daemon started or provider launched
by this entrypoint. The normal `session-policy.yml` still checks real ordinary
credentials before rendering or full activation.

After successful execution, `chaldea_client_policy_gate_evidence` contains the
environment, resolved runtime, sandbox SHA256, exact public policy/loader/CLI/
Node/checker/unit SHA256s and systemd invocation ID. The oneshot uses
`RemainAfterExit=yes` so evidence is captured while the completed invocation is
still active/exited. The role rechecks that exact invocation before stopping the
gate and hands back the captured evidence after confirming inactivity. It never
depends on InvocationID surviving inactive-unit garbage collection and does not
rerun the loader to recover metadata. If interrupted before stop, the retained
gate stays active/exited and admission refuses another execution; preserve its
metadata and use the parent's reviewed capture/stop cleanup. Check mode produces
no receipt. The packet controller must validate those exact bindings against its
source-pinned staged runtime manifest and approved environment before enrollment,
and refuse stale or mismatched evidence. This is evidence to validate, not an
enrollment bypass flag. Synthetic tests do not qualify the maintained loader on
a host; the separately approved host run remains required.

For one bounded system owner, call only `waits-system.yml` with the existing
system-mode inputs and `chaldea_client_waits_deadline: "YYYY-MM-DDTHH:MM:SSZ"`.
The target clock must report 16..2700 seconds remaining. Invalid, expired or
out-of-range deadlines fail before writes. The final unit is installed before
start, disabled at boot, has `Restart=no`, no Install section and a finite
2700-second safety limit. The small Node launcher rechecks the original absolute
deadline at every actual start and execs GNU `/usr/bin/timeout` around the exact
staged Node/Chaldea command. Both startup checks use the same bound. It reserves ten seconds before that deadline for
execution/shutdown, with TERM then KILL after five seconds. No timer or extra
Node supervisor is installed. This assumes a trustworthy host clock and standard
kernel scheduling; the parent packet must retain clock-health evidence.

A private `~/.local/state/chaldea/waits-bounded-starts.json` record reserves
the original deadline/runtime/environment with `starts: 0` after ownership
admission and before any bounded executable files are installed. An interruption
before first launch cannot authorize a later deadline; same-deadline recovery
reuses the reservation without renewing it. Each actual start then consumes an
attempt before execution. Do not delete or rewrite the record to retry a failed
launch. Corrupt, foreign or unsafe records fail closed. After terminal reporter
completion, the packet may stop the system owner and request one restart with
`chaldea_client_waits_status_read_restart: true` while enough original time
remains. The owner must already be inactive. The helper durably authorizes and
consumes this second start; further starts fail. The packet must prohibit new
reporter sessions during this status-read phase. The role starts no reporter
and does not change Chaldea's session authorization API. Capture this record,
the helper, new gate unit and existing restart-intent/backups in the parent's
write-ahead cleanup ledger. Bounded mode suppresses timestamped config/unit
backups because the parent's fixed capture retains the original bytes; persistent
mode retains its backups. This role does not implement composed cleanup.

An active bounded owner refuses configuration changes instead of restarting.
Repeated validation does not renew the deadline or consume a start. Namespace
and loader probes intentionally execute when requested; their service tasks
report a change even when all managed file bytes are converged. Empty deadline
preserves the persistent unit bytes and ordinary restart-intent recovery.

## Tests

The two canary public-render fixture cases require actual UID 0 ownership. They
run on agent-a and explicitly skip on ordinary CI users, with the root-case job
evidence retained separately. This is the smallest change that keeps production
root-owner acceptance intact without making CI privileged. A fresh-interpreter
test checks non-root collection and skip behavior by simulating UID selection;
agent-a maps only UID 0 and cannot establish a nested user namespace for an
actual unprivileged subprocess. This simulation is not ordinary-user runtime
qualification. Other canary tests still execute on ordinary CI.


`tests/test_chaldea_session_policy.py` applies the real role with the protected
root, owner and become replaced by extra vars, so the policy renders into a
scratch tree. It covers the default (no file, unchanged `waits.json`), check
mode, the exact rendered policy and its protected layout, a second converge
with no change, a policy without enrollments, each unsupported enrollment or
preset value, unsafe app-password files and unprotected policy paths, all
refused before any write, and that no fixture secret reaches the output.

`tests/test_chaldea_client.py` applies the real role under an asserted scratch HOME with a fake systemctl. It covers apply, repeat apply and check-mode idempotence, interrupted reload recovery, preflight before unit replacement, enabled services, missing/unsafe secret refusal, legacy checkout migration, preservation of config/state, rendered `%h` units, release retention, checksum/manifest/path/link refusal and disabled services without credentials. It never opens the live tokens or user manager.

Run tests through Chaldea with `TMPDIR` and `HOME` set to disk-backed job scratch. The existing `tools/ci.sh` runs these tests alongside the fleet checks, and activates a synthetic client during full-site double convergence to catch shared-directory permission conflicts.
