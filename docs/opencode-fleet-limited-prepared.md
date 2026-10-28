# Limited OpenCode on agent-a, agent-b and omarchy-pc

This batch selects the existing limited OpenCode composition in each host's
`inventory/host_vars/<host>/chaldea-jocasta-tooling.yml` and the existing ordinary
Jocasta plugin in each `jocasta-interactive.yml`. It is source only and remains
inactive until merged. Ordinary pulls can activate these selections after merge,
so root retains enrollment, qualification, merge and rollout authority. No live
readiness is claimed.

## Selected configuration

`docs/examples/opencode-fleet-limited.yml` remains public composition data
outside inventory, not an extra-vars file or role input. Its bindings and
workspaces record the independent host-local reads in
`HOST-BINDINGS-CURRENT.json` from 2026-10-26. The regression tests require each
inventory selection to equal `compose(host, bindings)` and pin those exact IDs.
Composition still refuses missing, malformed, shared or laptop-copied IDs.
omarchy-pc keeps its existing waits environment
`94023493-6346-46a6-8ca0-3c7d7ef28644` inline in `inventory/hosts.yml`.

Each host selects exactly one ceiling, preset, enrollment and profile named
`jocasta-tooling-opencode`. The existing laptop selection supplies the reviewed
shape, reporter prompt and read-only grant. Only host-local bindings, account,
native architecture and workspace differ.

- Waits uses persistent system mode with no deadline and the separately staged
  `/home/igor/.local/share/chaldea/releases/client-v0.4.20`. Published archive
  SHA-256 is `ed3376ab8f21c1b6bb7b2d03e9e8c074dd43ed25be4881aafe574a12e8b618ff`;
  manifest SHA-256 is
  `c8542918859a19ec99065117c5bd359a12de1838d6f54a4090f5e1ee12a2d2d1`.
  Ordinary `current` remains client-v0.4.11 with its existing rollback history.
  Node stays 26.10.0, with no legacy admission exception. The maintained
  user-to-system migration and its strict ownership guards are unchanged.
- Policy keeps project `tooling`, 1800 seconds, `delegate: false`, audience
  `jocasta` and `get/history/list/search` on `project:tooling`. The preset uses
  `opencode-jocasta-tooling`, model `opencode/nemotron-3.5-lightning-free` and
  no options. It differs from the laptop's `opencode/big-pickle` only because
  Big Pickle returned OpenCode's free usage limit on 2026-10-28; see the model
  selection section below.
- Enrollment uses the existing Jocasta tooling provider and one ordinary account
  per host, `chaldea-<host>-jocasta-tooling-opencode`, with 300-second tokens.
  homelab-infra owns enrollment and delivery to
  `/home/igor/.config/chaldea/authentik/jocasta-tooling-opencode.app-password`.
- The protected x86-64 OpenCode 2.1.3 native stays at
  `/home/igor/.local/share/chaldea/provider-assets/opencode/2.1.3/opencode`,
  SHA-256 `4c2630769fa853343a781e765b2280fc1a07f33f7c10d484f75d59e61eb85bc3`,
  240306352 bytes, ELF machine 62. Registry archive
  `@opencode/cli-linux-x64` 2.1.3 has SHA-256
  `c251bb3962813919d5eb8c0f43cd1cb3ab1d7a0cd28b2e556985706413005cb0`,
  member `package/bin/opencode`. It is separate from ordinary OpenCode 2.1.4.
  Private 0700 home and tmpdir stay under
  `/home/igor/.local/state/chaldea/profiles/jocasta-tooling-opencode/`.
- agent-a and agent-b use cwd `/home/igor`. The PC project
  `cbddbdc3-07f6-4089-ad38-19cae918fc8d` requires cwd
  `/home/igor/.local/state/chaldea/session-workspaces/jocasta-tooling-opencode`.
  Stock T3 forbids duplicate active project workspaces, and the protected launcher
  asserts exact cwd. The existing profile validator already accepts this private
  subdirectory; no guard or role change is needed.

The ordinary consumer selects only
`webmcp_interactive_opencode_state: present` through the existing fleet plugin.
Claude and Codex retain their full managed Jocasta selections. Helper and
enrollment sources, laptop values, HoloNet profiles/provider/policy, OV and all
other neighbors stay unchanged. The tool allowlist and prompt do not enforce
authorization; the Jocasta verifier and token project claim do.

## Model selection

The launcher sets `OPENCODE_DISABLE_MODELS_FETCH=1` and supplies no OpenCode
credential, so the protected native sees only its bundled models snapshot and
enables only zero-cost `opencode/*` models. A model is usable here only if the
pinned 2.1.3 native lists it in that state, independent of what a newer
ordinary OpenCode shows.

On 2026-10-28 a credential-free Chaldea job on agent-a downloaded
`@opencode/cli-linux-x64` 2.1.3, matched both pins above and ran
`opencode models --standalone` in scratch with the launcher's environment and
the protected policies (Chaldea jobs `31a0bbd5-0aa9-4d68-9353-e2c6a2cfc274` and
`e7cf290b-5e6d-4b68-89d3-ab89c195b3ce`). It listed 11 free models, matching the
count from the earlier native readiness. `nemotron-3.5-lightning-free` is among
them and is also active, zero-cost, tool-calling and option-free in the public
catalog at `https://models.opencode.ai/api.json`. Its text-only input matches
Big Pickle. `mimo-v2.6-flash-free` met the same checks and is the named
alternative.

These are listing facts only. No model turn ran. Whether OpenCode's free usage
limit is pooled per model, per client or per network address is not published,
so the replacement can still hit the same limit. Native tool calling, the
reporter JSON and completion need the same native qualification as before.
No paid provider, credential or automatic fallback is configured.

The existing local Ollama provider on omarchy-pc was considered and not
selected. The protected config defines only the Jocasta MCP server, so using it
would add a provider block to the role template, a new validated profile field
and an HTTP LAN destination that the profile URL rule refuses today. That
changes every rendered `opencode.json` and launcher on these hosts. agent-a and
agent-b would also depend on the gaming PC being awake and its GPU being free.
It remains a separate, larger follow-up.

## Evidence and remaining gates

The supplied staging evidence reports runtime, native and empty private directory
checks passing on all three hosts, with normal cleanup retention passing.
The PC retention result covers the selected role only; full-fleet REAL remains
deferred on an unrelated agent-tools diff. Dedicated projects are registered.
Node 26.10.0 isolated .20 load and the installed issuer schema are qualified.
These facts do not establish native or service acceptance.

The three new limited accounts are not live enrolled. Root must complete their
existing-only-provider enrollment and host-local secret delivery, register each
protected provider with binaryPath
`/etc/chaldea/sessions/jocasta-tooling-opencode/exec`, and qualify actual native
tooling read, other-project denial, exact service/helper/provider identity,
status, completion and cleanup. Ordinary OpenCode also needs its per-host native
acceptance before merge. Root retains the exact user-unit/backup admission and
system-service preflight gates in `docs/waits-system-preflight.md`.
Broader denied dispatch through injected T3 tools and real in-flight renewal or
reconnect remain unqualified, as on the laptop.

The per-host `chaldea-staging-retention.yml` files retain .20 while ordinary
user-mode .11 still converges. They preserve current/previous and existing
rollback history, keep pruning and do not install absent versions. Root rechecks
retained runtime and pinned Node before activation.

System mode converges waits only. Shared client, quota, collector and role
`mcp.json` stay as last converged. The PC's existing
`mcp_registrations_chaldea_waits_enabled: true` remains unchanged and uses the
current .11 client against `~/.config/chaldea/waits.json`. System mode changes
that file to the system socket `/run/chaldea-waits-1000/waits.sock` and adds
`sessionPolicy`. Root separately qualifies that fresh .11 consumer against the
actual system .20 service before the PC moves. No MCP version selector or
server-list override is added.

## Integration and rollback

Source tests, an independent final review pair and CI precede root's gated merge.
The PR remains draft while enrollment and native gates are pending. Rollout order
is agent-a, agent-b, then omarchy-pc, checking each before the next. This source
batch performs no installed configuration change or Ansible rollout.

For one host, remove its new limited selection and follow the system-to-user
rollback packet in `docs/waits-system-preflight.md`. Remove its Authentik row
only through homelab-infra. Ordinary plugin rollback selects `absent`, removes
only the marked fleet plugin and needs a fresh OpenCode process to take effect.
Preserve Claude/Codex managed access and every neighboring registration.
