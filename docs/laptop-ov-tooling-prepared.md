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
The prompt's only MCP operation is `memory_stat`: first the granted node,
then the denied sibling
`viking://resources/homeassistant-api/ov-canary-denied-a63e197f`, then the
granted node again after a literal passive `/usr/bin/sleep 370` through the
normal native terminal. All three calls and the wait belong to ONE admitted
native run. Final JSON is at most 1000 UTF-8 bytes without content, metadata
values or headers. The passive wait adds no service grant or server capability.
Prompt, timing and disabled-server configuration are not authorization boundaries;
the OV verifier and its namespace claim remain authoritative.

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
`docs/sessions.md`, `src/session/admit.ts`, `src/session/lifecycle.ts`,
`src/session/t3.ts` and `src/session/credential.ts`; fleet profile contract is in
`docs/chaldea-client.md` and the existing role templates.
The installed runtime's `session --help` advertises OV.
Invocation, private-header acquisition, native allow/deny and renewal remain
unqualified. Help output proves syntax only.

Root reports identity enrollment and its literal zero-change repeat accepted:
`rc=0 ok=90 changed=0 failed=0 unreachable=0`, with credentials and baselines
preserved. All operation intervals are CLOSED. Root prepared the empty new
profile HOME, `.codex` and tmpdir under
`/home/igor/.local/state/chaldea/profiles/ov-tooling-codex`, UID 1001 and mode
0700. No model-provider login is confirmed; root's device-auth/file-store login
status question remains pending. No auth cache was copied. Root separately
revalidated the staged Codex 0.163.0 native, companion and catalog pins/sizes,
ordinary MCP names and existing project IDs. These are root's observations,
not physical-host claims made by these tests.

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

Native acceptance requires a user-started laptop T3 session and host-local
execution owner, supported start/provider/caller exposure and the independent
model login. The initial calls, passive wait and renewal call must stay inside
its one admitted native root run. This PC thread cannot launch or inspect
another host's native T3 thread. Add no direct remote launch or proxy.

## Convergence, acceptance and cleanup

Root performs only the approved coordinated delivery after the gates above.
The isolated profile fixture must repeat with `changed=0`. For the full-site
limited laptop convergence, retain only the runbook's known namespace-probe
exception, with unchanged managed bytes and service invocation,
`failed=0`, `unreachable=0` and every other change reconciled. There is no blanket
zero-change waiver, and fixture idempotence is not live convergence evidence.

### One admitted run, with independent trace evidence

Chaldea `src/session/lifecycle.ts:225-265` captures the terminal root result,
finishes the session and releases occupancy when quiescent.
Its `issueGate` at lines 292-305 refuses `no_active_run`, `run_inactive` and
`preset_changed`. `src/session/admit.ts:11-25` refuses per-start prompt,
runtime and limit overrides. Therefore the former reporter's terminal result
with `renewal: NOT_RUN` could not support a later follow-up renewal test.
A separate session or changed preset cannot repair that missing same-run proof.

The corrected fixed prompt contains the complete sequence before admission:

1. Native `ov_tooling.memory_stat` for the granted documentation node succeeds.
2. Native `memory_stat` for the explicit denied sibling is refused by the server.
   These first two calls are the basic metadata-only initial probe.
3. The normal built-in terminal executes ONLY the literal `/usr/bin/sleep 370`.
   If the native interface yields a process/session handle, its normal
   continuation/wait interface waits for that exact process with no input until
   successful exit. No other command, shell expression, background process,
   local file/data operation, web, delegation, helper or MCP operation is allowed.
   The admitted native run must remain naturally active during this wait.
4. Before final output, the same native root run calls `memory_stat` on the
   granted node again and requires success. Finish only after the wait and this
   second granted call, except for a safe failure or unavailable prerequisite.

The 370-second wait exceeds the 300-second JWT lifetime plus potential
30-second future-`iat` and 30-second expiry grace, with margin, within the
unchanged 900-second run ceiling. Never fake a clock, stretch TTL, suppress
active-run checks, keep a terminal session artificially alive or edit policy
midrun. A call failure, unexpected allowance/denial, unavailable normal terminal,
failed wait or insufficient remaining deadline stops safely with FAIL or
INCOMPLETE and no renewal PASS.

Root must independently bind successful before/after native RPCs, denied
sibling, measured elapsed time >=370 seconds, admitted session ID, native
thread/run, provider/model/options, exact pinned profile and timestamps.
Sleep execution or model report alone is not acceptance. Final reporter JSON
uses `v/status/allowed/denied/renewal/issues`, at most 1000 UTF-8 bytes and no
content, metadata values, credentials or headers. Renewal PASS requires the
actual second successful native RPC AND root's trace verification. Until that
verification is available the fixed reporter returns INCOMPLETE with
`TRACE_VERIFICATION_REQUIRED`; root records acceptance separately from the
exact stored reporter bytes. No final result or follow-up is used to keep the
old run active. Retain one correlated completion delivery, runtime exit and
released occupancy as separate observations.

The existing pinned launcher in
`roles/chaldea_client/templates/codex-profile-exec.py.j2:45-56` still passes
`features.shell_tool=false`. This correction changes no launcher flag, model
catalog, profile or native pin. Whether this exact stock Codex 0.163.0 code-mode
terminal exposes a usable passive terminal/continuation interface remains
UNQUALIFIED. Native tools may expose `exec_command`/`write_stdin` equivalents;
use only the interface actually supplied. If none can perform the literal wait,
retain INCOMPLETE and the exact interface/source gap. Add no clock tool,
scheduler, helper or framework, and claim no exclusive catalog containment.
The source/config/parser and synthetic actual-role checks do not execute the
370-second wait or qualify native terminal availability.

### Issuance stops after completion

After the successful native run reaches terminal state and release, root may
exercise the maintained private native headers helper through a protected
operator harness. That harness must capture all helper stdout/header bytes
privately and report only refusal code and exit status. Expect the ordinary
`run_inactive` or `no_active_run` refusal, bound to that completed run and preset.
This is a separate actual gate test, never an ordinary model-visible headers
call, token extraction, gate bypass or Authentik identity mutation.

The source completion/refusal behavior plus that future protected-harness test
does not prove failure of an in-flight refresh, exclusive catalog containment
or immediate revocation of an issued offline token. No such claim is made.
If the maintained private mechanism or evidence binding is unavailable, retain
that explicit gap. No new mechanism is supplied by this draft.

Rollback reverses activation: prevent new starts by removing the preset or T3
provider, move the profile to `chaldea_client_session_profiles_absent` as
`{name: ov-tooling-codex, home: <profile home>}`, remove only its enrollment and
ceiling, then converge. The profile HOME and login remain for root's explicit
retirement. Remove the Authentik identity only through its infra entrypoint and
original receipts. Preserve the controller credential, other-owner state,
existing OV route/runtime/issuer and bounded canaries.

The focused tests cover exact real inventory values, all-original-value
preservation, unchanged non-prompt OV configuration, ordered same-run reporter
protocol, widened/shared refusals and actual role render/check/delivery/
idempotence with synthetic assets and an unopened FIFO login stand-in.
They establish no actual login, provider registration, caller admission,
token acquisition, server denial, renewal or native acceptance.
