# Laptop limited OV tooling Codex: prepared candidate

Source preparation only. `docs/examples/laptop-ov-tooling-codex.yml` is outside
inventory and no role loads it, so a normal pull or converge changes nothing.
No enrollment, credential delivery, profile delivery, T3 provider change or
session has happened because of this file.

## What the candidate is

One fixed, nondelegating Codex preset, `ov-tooling-codex`, with exactly one
service: OV, scope `ov.read`, `ov_namespaces` exactly
`[viking://resources/homeassistant-api/rest-api.md]`. That is the same node the
existing OV canary reader holds and nothing wider.

- Ceiling: a new entry for local project `tooling`, 900 seconds, destination
  `f29ad608-ef74-42e2-bc34-1d8c4f4c8dc5`, services exactly the preset's one
  OV grant. The existing Jocasta ceiling is not changed, and neither ceiling
  admits the other service's presets.
- Preset: the Jocasta Codex preset's model `gpt-6.1-sol`, `reasoningEffort`
  high, `approval-required` runtime and T3 project
  `mcp:2fe01b0e-5727-4111-9b95-ff81508562ba`, with its own T3 provider
  instance `codex-ov-tooling`. The reporter calls only `memory_stat` on the
  granted node and on the denied sibling
  `viking://resources/homeassistant-api/ov-canary-denied-a63e197f`, and returns
  compact JSON under 1000 bytes with no content or headers. It reports
  `renewal: NOT_RUN`; the prompt never waits, so it cannot pretend to prove
  renewal.
- Enrollment: ordinary account `chaldea-laptop-ov-tooling-codex` on the
  existing OV provider (`ov-http-a63e197f-machine`, issuer
  `https://auth.ryzhkov.dev/application/o/ov-http-a63e197f/`), 300-second
  tokens, app password at
  `/home/igor/.config/chaldea/authentik/ov-tooling-codex.app-password`. It is
  created by homelab-infra's `playbooks/authentik-ov-http-identities.yml`,
  never by copying the controller's OV credential or a Jocasta credential.
- Profile: the qualified Codex 0.163.0 native, companion and catalog pins of
  the Jocasta Codex profile; a new profile home
  `/home/igor/.local/state/chaldea/profiles/ov-tooling-codex/home` with its
  own Codex login; MCP server `ov_tooling` limited to `memory_stat`; and the
  operator servers `chaldea`, `huyang`, `jocasta` and `ov-memory` neutralized.

The tool allowlist and prompt are not the authorization boundary. The OV
server's verifier and the token's `ov_namespaces` claim are.

## Client support

The fleet enrollment and profile validators already accept closed OV presets;
this change adds no validator or role code. Root observed on 2026-10-25 that
the laptop's installed waits runtime, client-v0.4.18 with Node 26.12.0,
answers `session --help` with
`chaldea session headers --preset NAME --audience jocasta|ov|homelab|ha`.
That proves the installed command accepts `--audience ov` as invoked. Token
issuance, signed-token acceptance by the OV verifier and same-session renewal
through a native session remain unqualified.

## Inputs root binds before activation

1. The infra enrollment of `chaldea-laptop-ov-tooling-codex`, completed and
   verified, with its app password delivered only to the laptop as UID 1001.
2. The laptop's Codex 0.163.0 assets at the pinned paths, rechecked by size and
   SHA-256.
3. A provisioned profile home and tmpdir, mode 0700, with an independently
   supported Codex login created in that home. No auth cache is read, copied
   or moved from another home.
4. The laptop operator Codex configuration's actual MCP server names,
   confirmed covered by `disabled_servers`, and the native session's effective
   MCP list showing only `ov_tooling` plus T3's own control tools.
5. The T3 Codex provider instance `codex-ov-tooling` with
   `binaryPath: /etc/chaldea/sessions/ov-tooling-codex/exec` and
   `homePath: <profile home>/.codex`, created only after the profile is
   delivered.
6. Caller and session project IDs rechecked against the laptop's live T3 and
   policy, as root did for the existing presets. Do not reuse them for any
   other host.
7. The coordinated writer interval with the laptop's other owner: the waits
   runtime stays client-v0.4.18 and its current selection is preserved.

## Activation and rollback

Activation is a separate reviewed inventory change that merges the four
entries into `inventory/host_vars/laptop/chaldea-jocasta-tooling.yml`. It must
not reach main ahead of the inputs above, because the laptop pull applies main.
Then converge, confirm a second converge reports no changes, and run the native
qualification: the granted `memory_stat` call, the sibling denial, the separate
more-than-330-second same-session call and failed-issuance behavior.

Rollback reverses the order: remove the preset or T3 provider instance so no
session can start it, move the profile to `chaldea_client_session_profiles_absent`
as `{name: ov-tooling-codex, home: <profile home>}`, remove the enrollment and
ceiling, and converge. The profile home and its login stay in place for root to
retire. The Authentik account is removed only through the infra entrypoint by
declaring the laptop identity absent.

`tests/test_laptop_ov_tooling.py` checks the candidate's exact values, runs
the role's validators over the real laptop maps with the candidate merged,
refuses widened or shared variants, renders the policy from the real inventory
and delivers the profile through the actual role in a scratch tree.
