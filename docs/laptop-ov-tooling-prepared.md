# Laptop limited OV tooling Codex activation draft

DRAFT HOLD UNTIL root completes the protected inputs below, independent reviews
and CI. This branch adds the reviewed OV entries to the full owning maps in
`inventory/host_vars/laptop/chaldea-jocasta-tooling.yml`. Merging to main can
activate them through the laptop pull timer. Do not merge, pull this branch on
the laptop or make this inventory effective ahead of those gates.

The approved packet is `jocasta:4d83809041500fe14575e39476e13c04@2`; revision 3
retains the accepted operator-trust and evidence caveats. The maintained runbook
is `jocasta:38a63cf8918eebae2dd7c8911eacd89c@34`. Root owns live execution,
reviews, CI acceptance, coordination and cleanup. This draft performs no live
credential, model, provider, helper or native call.

## Exact source scope and preservation

The desired-value reference remains
`docs/examples/laptop-ov-tooling-codex.yml`. It is outside inventory and no role
loads it. Never pass it as extra vars. The owning hostfile adds only:

- A separate 900-second `tooling` ceiling for destination
  `f29ad608-ef74-42e2-bc34-1d8c4f4c8dc5`.
- The nondelegating `ov-tooling-codex` preset naming `codex-ov-tooling`,
  `gpt-6.1-sol`, `reasoningEffort: high`, `approval-required` and session project
  `mcp:2fe01b0e-5727-4111-9b95-ff81508562ba`.
- Its independent enrollment, `chaldea-laptop-ov-tooling-codex`, on the existing
  OV issuer `https://auth.ryzhkov.dev/application/o/ov-http-a63e197f/`,
  client ID `ov-http-a63e197f-machine`, 300-second tokens and protected
  `/home/igor/.config/chaldea/authentik/ov-tooling-codex.app-password`.
- Its fixed Codex profile, server `ov_tooling`, endpoint
  `https://ov.mcp.ryzhkov.dev/mcp`, tools exactly `[memory_stat]`, and independent
  HOME `/home/igor/.local/state/chaldea/profiles/ov-tooling-codex/home` and tmpdir
  `/home/igor/.local/state/chaldea/profiles/ov-tooling-codex/tmp`. The cwd stays
  `/home/igor`. Ordinary MCP names `chaldea`, `huyang`, `jocasta` and
  `ov-memory` are disabled in this profile.

The one service is exactly `ov.read` and
`ov_namespaces: [viking://resources/homeassistant-api/rest-api.md]`.
The prompt calls only `memory_stat` for that node and the denied sibling
`viking://resources/homeassistant-api/ov-canary-denied-a63e197f`, then returns
compact JSON below 1000 bytes without content or headers. It reports
`renewal: NOT_RUN` and never waits. Prompt and disabled-server configuration
do not replace the OV verifier's server ACL.

Both original Jocasta entries, their 1800-second ceiling, all model/native pins,
HOME/cwd, expiry, grants and destinations, ordinary client settings and timers
remain unchanged. Runtime stays client-v0.4.18 and Node stays 26.12.0.
No OpenCode entry, runtime 0.4.20, role, helper, daemon or merge framework is added.
No second hostfile overrides the owning maps.

Before editing base `15f1950c1222b40a51630fb8331386db38902d75`, agent-a measured the
owning hostfile byte SHA-256
`441e80835b8bff6dd3ade5a11b632c35015e593d2c017273e52efaf4116bd5a7`
and canonical semantic SHA-256
`c810430f87db92769cecb239c1a7270df06dc8f001181b9329ebc3843ffa8e37`.
The focused regression removes only the four OV additions and requires the
complete remaining hostfile to recover that semantic digest. Original Jocasta
field assertions remain, and the real inventory's complete policy is rendered
through the role without session-map overrides.

Fleet PR112 belongs to another owner and remains separate pending their user
decision. This draft deliberately changes the owning hostfile. Their future
rebase must preserve these additions and every original Jocasta value; root must
review the combined semantic diff before any convergence. This branch does not
edit their generic files or authorize their work.

## Client seam and unqualified prerequisites

Source inspected at Chaldea `839eadc615a1c5c977992a418f40a9366cea6594`:
`docs/sessions.md`, `src/session/admit.ts`, `src/session/t3.ts` and
`src/session/credential.ts`; fleet profile contract is in
`docs/chaldea-client.md` and the existing role templates.
The installed runtime's `session --help` advertises OV.
Invocation, private-header acquisition, native allow/deny and renewal remain
unqualified. Help output proves syntax only.

Root reports first identity enrollment succeeded and independently rechecked the
delivered credential's public custody metadata. The staged Codex 0.163.0 native,
companion and one-model catalog matched the reviewed pins and sizes. The live
ordinary MCP names and existing project IDs were also revalidated. These are
root's separate observations, not physical-host claims made by these tests.

Before merge, root must bind and retain all of the following:

1. An independently supported model-provider login in the new profile HOME,
   with owner-only HOME and tmpdir, and an owner-only `.codex` directory.
   The role only stats those directories and writes `.codex/config.toml`.
   It neither creates a login nor reads, copies or migrates an auth cache.
   Creating the OV service credential does not complete this model login.
2. Dedicated T3 provider registration `codex-ov-tooling` with
   `binaryPath: /etc/chaldea/sessions/ov-tooling-codex/exec` and
   `homePath: /home/igor/.local/state/chaldea/profiles/ov-tooling-codex/home/.codex`.
   Its registration and executable binding must be coordinated with delivery;
   it cannot launch until the protected profile exists. This role supplies the
   launcher and native MCP configuration, not the provider registration.
3. Caller admission and accounting bound to the actual laptop T3 environment
   `943bead7-d804-4e04-984e-63d230303796`, a live root caller thread in destination
   `f29ad608-ef74-42e2-bc34-1d8c4f4c8dc5`, and the existing session project above.
   The start interface is only `chaldea_session_start {threadId, requestId, preset}`.
   Use the real caller thread, one saved idempotency key and preset
   `ov-tooling-codex`; do not invent an ID or pass per-start grant reductions.
   Existing unrelated caller ceilings stay at 1800 seconds. The OV preset must
   fit its own complete 900-second ceiling. Session descendants cannot delegate.
   A supplied thread ID and same-UID socket access are operator context, not
   authenticated per-thread confinement. Root must also qualify the caller's
   compatible Chaldea MCP registration against the client-v0.4.18 runtime and
   waits config naming the protected session policy. Source `src/mcp.ts` exposes
   `chaldea_session_start` only when that config enables sessions. Ordinary
   client/current and MCP settings remain unchanged here; neither their existing
   registration nor `session --help` proves that this caller can start a session.
   The `session` CLI supplies `headers`, not a shell `session start` interface.
   Do not change the ordinary registration or add a proxy to hide this gap.
4. Full actual CHECK reviewed before REAL, including public policy/profile
   validation, protected inputs and paths, credential custody, original Jocasta
   state, runtime selection, native pins and managed-file changes. Ansible extra
   vars are trusted operator inputs that can override source; root must inspect
   their complete contents. Do not infer qualification from a synthetic fixture.
5. A coordinated writer and cleanup window with the other laptop owner,
   recorded start/cutoff/hard deadline, writer/timer/service state, exact source,
   preserved other-owner state and receipt-owned rollback. Source merge itself
   can activate the laptop pull and is held until these protected inputs and the
   reviewed delivery/registration sequence are complete.

The existing header seam runs the pinned waits Node and resolved client-v0.4.18
`bin/chaldea session headers --preset ov-tooling-codex --audience ov --config
/home/igor/.config/chaldea/waits.json` from protected native MCP configuration.
The helper's stdout is private credential material; never invoke it in a
model-visible tool. The existing acquisition/cache/lifecycle stays authoritative.
No new credential mechanism or custom refresh is needed.

Native acceptance and the later same-session renewal call require a user-started
laptop T3 session and a host-local execution owner. This PC thread cannot launch
or inspect another host's native T3 thread. Keep this boundary; add no direct
remote launch or proxy.

## Convergence, acceptance and cleanup

Root performs only the approved coordinated delivery after the gates above.
The isolated profile fixture must repeat with `changed=0`. For the full-site
limited laptop convergence, retain only the runbook's known namespace-probe
exception, with unchanged managed bytes and service invocation,
`failed=0`, `unreachable=0` and every other change reconciled. There is no blanket
zero-change waiver, and fixture idempotence is not live convergence evidence.

Bind admitted session, actual native thread/run, provider/model/options,
installed source/profile, prompt and timestamps. Observe allowed-node
`memory_stat` and sibling denial through native HTTP MCP without storing
content, metadata values, tokens or headers. Separately bind a successful call
more than 330 seconds later in that same session to the original 300-second
token lifetime, and qualify issuance-stop/failed-renewal behavior. An issued
offline JWT may remain valid until expiry; claim no immediate revocation.
Retain exact final reporter bytes and one correlated completion delivery;
provider removal, process exit and released occupancy are separate checks.

Rollback reverses activation: prevent new starts by removing the preset or T3
provider, move the profile to `chaldea_client_session_profiles_absent` as
`{name: ov-tooling-codex, home: <profile home>}`, remove only its enrollment and
ceiling, then converge. The profile HOME and login remain for root's explicit
retirement. Remove the Authentik identity only through its infra entrypoint and
original receipts. Preserve the controller credential, other-owner state,
existing OV route/runtime/issuer and bounded canaries.

The focused tests cover exact real inventory values, all-original-value
preservation, widened/shared refusals and actual role render/check/delivery/
idempotence with synthetic assets and an unopened FIFO login stand-in.
They establish no actual login, provider registration, caller admission,
token acquisition, server denial, renewal or native acceptance.
