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

Inventory enables quota and waits on omarchy-pc. The laptop runs system waits with protected Jocasta tooling sessions; see [Laptop persistent activation](#laptop-persistent-activation). Other agent hosts default to both units disabled. Disabled units are installed, stopped and disabled; they require no credentials.

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

Off by default. `chaldea_client_session_policy_enabled: false` renders no
policy and leaves `waits.json` without a `sessionPolicy` key, byte for byte as
before. Only the laptop enables it, in its dedicated host_vars file.

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
stock T3 server starts the stock Codex or Claude binary through one rendered
launcher.

Off by default; only the laptop delivers profiles. `chaldea_client_session_profiles: {}` renders nothing. The
role delivers profiles from `waits-system.yml`, right after the protected policy,
so they require `chaldea_client_session_policy_enabled: true` in system waits
mode. Public validation runs with the other waits checks before any mutation.
The `codex` and `claude` drivers are supported, each with its own exact field
set; see [Claude profiles](#claude-profiles) for the second.

Each profile is keyed by a name matching `[a-z0-9][a-z0-9-]{0,47}`. A Codex
profile has exactly these fields; every one is an operator input:

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
      source: "<operator path to the reviewed catalog file>"
      sha256: ad005892044dec4f817f431ff75302193e27bbfb7533958afe6a91194fd7b784
      size: 65174
    elf_machine: 183                      # 183 AArch64, 62 x86-64
    model: gpt-6.1-sol                    # must equal the preset model
    home: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/home
    tmpdir: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/tmp
    cwd: /home/igor                       # the T3 server's working directory: fleet home or inside it
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

### Claude profiles

A Claude profile pins only the native binary. It has no companion, catalog,
home or temporary directory, and the role writes nothing in any home. It has
exactly these fields:

```yaml
chaldea_client_session_profiles:
  claude-tooling-reporter:
    driver: claude
    native:                               # already-installed official Claude binary
      source: "<operator path to the installed claude 2.1.276 ARM64 binary>"
      sha256: e9ac3df956083645578a382ad64ec304468666e362c33bfdefd803cd6ff596b0
      size: 231989488                     # at most 400000000
    elf_machine: 183
    cwd: "<the preset's reporter workspace root>"
    preset: tooling-reporter
    audience: jocasta
    server: jocasta_tooling               # not t3-code or t3_code
    url: https://jocasta.mcp.ryzhkov.dev/mcp
    tools: [get, history, list, search]
```

The same preset, enrollment, URL, tool and source pin checks apply as for Codex.
The role writes, as root and with no group or other write access:

| Path | Content |
| --- | --- |
| `/etc/chaldea/sessions/<name>/claude` | native binary, byte for byte, 0755 |
| `/etc/chaldea/sessions/<name>/claude-settings.json` | protected permissions, 0644 |
| `/etc/chaldea/sessions/<name>/mcp.json` | public MCP description, 0644 |
| `/etc/chaldea/sessions/<name>/exec` | launcher, 0755, written last |

The protected settings allow exactly `mcp__<server>__<tool>` for the profile
tools and deny the fixed role list in `vars/main.yml`: the T3 control tools,
Bash, PowerShell, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch and Agent.
`mcp.json` has the same form as the Codex one.

The launcher is the accepted fixed Claude reporter launcher with its literals
rendered from the profile and its single-run receipt removed. It writes nothing
and starts no process other than the native binary. At each start it admits only
the fixed T3 argv shape: `--restricted`, `--strict-mcp-config`, `--mcp-config`
equal to this profile's `mcp.json`, empty `--setting-sources`, empty tools,
default permission mode, stream JSON, the T3 control tool denial, `--add-dir` of
the profile `cwd` (optionally with T3's attachments directory, which it drops),
and one `--settings` object limited to the known SDK keys. It refuses shell
expansion syntax and duplicate JSON keys. It then requires the fleet UID and
the profile `cwd`, reads the protected settings by directory descriptors
without following links, requiring the exact rendered SHA-256 and exactly the
protected permissions, and replaces the session permissions with them. Finally
it pins the native binary by descriptor, SHA-256, ELF machine and execute bit,
and executes it with the inherited environment. The `--version` probe needs
only the UID and native checks. Any failure exits 78 with `FIXED_EXEC_REFUSED`.
The launcher accepts protected files owned by root or the fleet UID that no one
else can write, as the accepted launcher did; the role still delivers them
root-owned. It does not hash `mcp.json`; Claude reads that file itself, so its
integrity rests on root custody of the profile directory and the role's
delivery hash check.

To enable a Claude profile, create the T3 Claude provider instance with
`binaryPath: /etc/chaldea/sessions/<name>/exec` and these launch arguments,
then name that instance in the preset:

```text
--restricted --strict-mcp-config --mcp-config /etc/chaldea/sessions/<name>/mcp.json
--setting-sources '' --settings /etc/chaldea/sessions/<name>/claude-settings.json
--tools '' --disallowed-tools 'mcp__t3-code__*,mcp__t3_code__*'
```

### Optional Claude capability probe

A Claude profile may explicitly set `capabilities_probe: true` to recognize only
the two stock T3 0.1.0 / SDK 0.3.276 initialization argv shapes. This defaults
off; absent or false keeps the pre-probe launcher bytes identical. HoloNet selects
it, while its admission switch remains off. Existing Jocasta profiles do not opt in.

T3's auxiliary health query omits provider launchArgs and asks for user/project/local
setting sources. Passing it through would violate the conversation contract.
The optional branch accepts the complete finite argv, then replaces it with
restricted initialization, empty setting sources, hooks disabled, no tools,
strict empty MCP config and all MCP tools denied. It pins the same protected
policy/native bytes, uses only the fixed profile cwd, disables connected Claude
MCP and IDE discovery in the child environment, and never passes a credential
helper or catalog grant to the probe. All other shapes still refuse. There is no
auth-CLI passthrough, unrestricted fallback or changed conversation parser.

The upstream health caller waits for initialization with a never-yielding prompt.
The argv itself cannot authenticate that caller or prevent another same-UID caller
from submitting stdin. This is not a hostile-process sandbox. Even such a caller
gets the probe's empty tool/MCP permissions, not the profile's service grant.
Successful metadata initialization still does not qualify a model turn, MCP ACLs,
stored results or renewal. Those require separate real native acceptance.

### Rollback

The guarded inverse removes a retired profile's role-owned files. First remove
the preset (or disable the session policy) and the T3 provider instance that
uses the launcher, so no session can start it. Then move the profile from
`chaldea_client_session_profiles` to:

```yaml
chaldea_client_session_profiles_absent:
  - name: codex-tooling-reporter
    home: /home/igor/.local/state/chaldea/profiles/codex-tooling-reporter/home
  - name: claude-tooling-reporter
    driver: claude
```

A retired Codex profile is exactly `{name, home}`; a retired Claude or OpenCode
profile is exactly `{name, driver: claude}` or `{name, driver: opencode}`. A normal converge, or the role-only
`session-profiles-absent.yml` entrypoint, removes the launcher first, then the
other protected files (for Codex also `<home>/.codex/config.toml`), and finally
the profile directory with `rmdir`. It refuses links, non-root files and foreign
directories before removing anything, and stops if anything unknown remains in
the profile directory. The profile home, its login and the source binaries are
left in place. A name cannot be delivered and retired in the same run.

### OpenCode driver

The [laptop OpenCode selection](laptop-opencode-prepared.md) records the
selected laptop profile and the root-owned staging and native acceptance gates
that precede its merge.

An OpenCode profile names the pinned official `opencode` native (`native`,
`elf_machine`), an operator-provisioned private `home` and runtime `tmpdir`
(both owned by the fleet user, mode 0700, never read or written by the role),
the T3 server `cwd`, and the usual `preset`, `audience`, `server`, `url` and
`tools`. The role delivers `opencode`, `opencode.json` and `exec` under the
protected profile directory. `opencode.json` holds the single remote MCP entry,
whose Authorization header is `{file:jocasta.authorization}`, and instance
policies: every tool denied except `<server>_*` and T3's own `t3-code-*`, and
every MCP integration removed except those two. The T3 OpenCode provider
instance points `binaryPath` at `exec`; ACP is not used.

The launcher admits only `serve --hostname=127.0.0.1 --port=N` and `--version`.
It stays the foreground parent of one native child in T3's process group, with
a fixed environment: the private home as HOME and XDG roots, project, Claude
and plugin config disabled, and only T3's serve password passed through. Each
launch gets `<tmpdir>/opencode-<random>/` (mode 0700) holding `tmp/` for the
child's TMPDIR and `config/`, the child's OPENCODE_CONFIG_DIR, with a copy of
the protected `opencode.json` and the header file (mode 0600), replaced
atomically; OpenCode watches that directory and reconnects with the new header.

The launcher calls the existing headers helper without a shell, first with
`--context`, then before each expiry with `--context --expect-session
--expect-run --expect-deadline` bound to the original admission. It renews 25
seconds before expiry, inside the helper's 30-second cache threshold, with a
10-second helper timeout. The first refusal, an unchanged or too-short header,
a changed session, run or deadline, the original deadline, a missed renewal,
a changed config copy, a stop signal or the child's exit ends the launch: the
owned process group gets TERM even after the direct child exits. After three
seconds, pidfd-bound KILL reaches surviving members without killing the
launcher or risking a reused PID. The launcher adopts orphaned descendants,
reaps children and allows at most three more seconds for KILL completion before
removing the launch directory. Helper completion rechecks elapsed boot time,
the original deadline and the previous header's stop margin before publication. There is no retry, restart or new session. The child dies with the
launcher through the parent-death signal. After an uncatchable kill the launch
directory stays behind; its header expires on its own and is not revoked.

### Limits

The launcher and file custody prevent accidents and stale or edited inputs;
they are not containment of a hostile process running as the same UID. The
profile home and `home/.codex` belong to the fleet user, so that UID can race
the checks, replace `config.toml` between launches, or swap a directory while
the role writes or removes the one root-owned file there. Codex, Claude and
their tools also run as that UID, and a Claude session inherits the T3
server's environment. T3 injects its own control tools and request-level MCP
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
Repeated validation does not renew the deadline or consume a start. The
credential-free namespace probe runs on every real run and any failure stops
it, but it reports no change, because it only reads; its definition and checker
report their own changes. The loader gate's service task still reports a change
when requested. Empty deadline
preserves the persistent unit bytes and ordinary restart-intent recovery.

## Laptop persistent activation

`inventory/host_vars/laptop/chaldea-jocasta-tooling.yml` is the laptop's desired
state for its first persistent read-only Jocasta tooling sessions, so the normal
pull converges the qualified state the reviewed maintenance left. It sets system
waits with the separately installed `client-v0.4.20` runtime (`client-v0.4.18`
plus only the session-bound headers helper the OpenCode driver needs; stage it
before this file reaches the laptop), an empty deadline,
the protected policy, the `jocasta-tooling-claude` preset (`claude-opus-5`, the
model the pinned Claude 2.1.276 accepts) with its Authentik enrollment and
fixed Claude profile, and the matching Codex and OpenCode presets, enrollments
and profiles. The grant is `get`, `history`, `list` and `search` on
`project:tooling`, 1800 seconds, `delegate: false`, destination the root caller's
T3 project. Each profile native comes from the operator-staged
`~/.local/share/chaldea/provider-assets/` copy. No other host and no interactive
provider, model or Chaldea MCP registration is configured by it.

The laptop's move from `client-v0.4.18` used a one-time admission of the exact
`client-v0.4.18` system unit (`chaldea_client_waits_legacy_system_runtime`, see
[system waits preflight](waits-system-preflight.md)). That admission is retired:
this file admits only the current `client-v0.4.20` unit and refuses the
`client-v0.4.18` one, so it must reach the laptop only after that migration.

Codex's first actual T3 launch exited 78; the operator traced it to the
launcher's fixed `cwd` naming the session workspace, while it must equal the T3
server's own working directory, the fleet home. The profile with
`cwd: /home/igor` then passed native acceptance (fleet PR105).

This branch adds the OpenCode selection (`opencode/big-pickle`, protected
native 2.1.3, private HOME and tmpdir, `cwd: /home/igor`). Its native acceptance
is root-pending: do not merge it or let a pull apply it before the gates in the
[laptop OpenCode selection](laptop-opencode-prepared.md) pass for this exact
source.

The file keeps its literal Jocasta inputs under `chaldea_laptop_jocasta_ceilings`,
`_presets`, `_enrollments` and `_profiles`. The role's
`chaldea_client_session_*` maps are composed from them in the same file, adding
the HoloNet Movies catalog input from
`inventory/host_vars/laptop/chaldea-holonet-catalog.yml` only while
`chaldea_laptop_holonet_catalog_enabled` is true. That flag is false, so each
effective map equals its Jocasta input and the rendered policy and profiles keep
their bytes. Jocasta entries are combined last, so a HoloNet name cannot
replace one. `ansible-inventory` shows the composition expressions
unevaluated; read effective values through a play, as the tests do.

The HoloNet input is one `holonet-movies-catalog-claude` preset, enrollment and
Claude profile: `catalog.read` on one server, one library and one catalog user,
no history or target users, 900 seconds, `delegate: false`, the pinned Claude
2.1.276 native and the single `catalog_query` tool on `holonet_catalog`. Its
fixed prompt makes six calls (two allowed pages, three ACL refusals, one bounds
refusal) and returns counts only. Setting the flag true is root-gated: it
requires the enrolled app password, the dedicated T3 provider instance
`claude-holonet-movies-catalog`, an installed headers helper that serves audience
`holonet`, and native acceptance of this exact source. Enabled, the pull stats
that credential and delivers the profile.

Consequences of the normal pull on the laptop:

- `chaldea_client` converges waits only: the shared client pin, quota unit,
  route/capacity files and `mcp.json` stay as last converged and no longer follow
  later shared client pin changes while the laptop is in system mode.
- `chaldea_node_version: 26.12.0` is host-wide, so the laptop's Chaldea MCP
  registration command, job-client launcher, collector and retention unit also
  use Node 26.12.0. The already rendered user quota and quota-sharing units and
  the reserved pre-system user unit keep 26.10.0. Retention protects only
  `chaldea_node_version`, so the file sets `retention_mise_prune: false`: the
  retention timer still cleans worktrees, temporary files and the Go cache but
  never runs `mise prune`. Keep it off while any 26.10.0 consumer remains.
- The credential-free namespace probe runs on every real converge and still
  stops the pull when it fails, but it reports no change, so a converged pull
  reports `changed=0` for this role. The waits service restarts only for
  pending restart intent.
- The waits tokens, answer token and every profile's app-password file must
  exist with owner-only modes, and the OpenCode private HOME and tmpdir must
  exist with mode 0700; a missing one stops the laptop's pull at this role.

Rollback is not a revert of this file alone. Default user mode refuses while the
system unit exists, so a revert merged first makes the laptop's pulls stop at
this role (fail closed, later roles in that run skipped) until the
target-specific packet in [system waits preflight](waits-system-preflight.md)
and the profile inverse above run. Running the inverse while this file is still
on main lets the next pull reinstall it. Coordinate both, inverse after merge.

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
