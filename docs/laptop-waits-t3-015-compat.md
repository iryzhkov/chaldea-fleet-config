# Laptop waits compatibility with T3 0.1.5

This source selects the already staged client-v0.4.23 for the laptop's sole
system waits owner. The exact .20 unit is admitted by the existing guarded
legacy_system_runtime mechanism. No role framework or deployment is added.
The parent owns independent review, merge and all runtime actions.

## Release provenance

GitHub's read-only release API on 2026-10-29 reports
[client-v0.4.23](https://github.com/iryzhkov/chaldea/releases/tag/client-v0.4.23),
published 2026-10-29T22:15:37Z, targeting commit
`2a9aec02d003969af1a1fa19e995a4934288c75b`, merged Chaldea PR99.
The tag ref independently resolves to that commit.

Downloaded public assets match the API digests:
- `chaldea-client.tar.gz`: SHA-256
  `b96c928d050d81e7be96841baf8ce0204927cd14fbd43b62cc0d4ac058fb9c82`
- `manifest.json`: SHA-256
  `443cdf3598fb146e03ff1010bda6753ff1780d78a5d860182eedf185ac89b41a`

The manifest names client-v0.4.23 and the same archive hash.
The parent's recovery packet maps all 219 tag-listed deployed files to the
installed .23. Its .20/.23 source comparison finds identical src/waits,
src/wake, src/session and src/t3/waits.ts, with no schema migration.
Inherited actual read-only getConfig, synchronized-shell and archive acceptance
passes on .23 against current T3 0.1.5. .20 rejects the expanded keybindings
during getConfig, before observer attachment. These are inherited qualification
receipts, not new live continuity checks.

## Expected canonical rollout scope

Relative to the installed .20 state, expect the system unit's single runtime
path to change to .23, its backup and persisted restart intent, and normal
guarded preflight/restart/readiness work. Fixed profile files can also change
the helper runtime path and dependent launcher digests. Tests cover these
helper-only changes for retained Claude/Codex definitions and protected OpenCode.

The installed fleet has not received merged fleet PR137 at base 534d6bb.
Canonical rollout therefore also includes its exact owned-file retirement of
inactive Jocasta Claude/Codex and HoloNet Claude profiles. Apply PR137's provider
quiescence and removal gates before activation. Ordinary Claude/Codex WebMCP
and the protected OpenCode definition retain their existing configuration.

Keep ordinary current .11/previous .9, Node 26.12.0, database, auth paths,
socket, environment, empty deadline and sole waits ownership. No new API,
daemon, store, permissions, credentials or provider enrollment is introduced.
Any additional canonical diff needs explanation before runtime convergence.
System mode skips client release retention. Preserve staged .23 and .20
explicitly before any separately scheduled release pruning is enabled.

## Recovery and finite acceptance

Do not restart unchanged .20 against T3 0.1.5. There is no compatible .20
operational fallback. Its compatible persistent schema does not make its
protocol adapter usable. Keep the explicit legacy admission until actual
convergence; retire it in a checked current-only follow-up. Tests retain
refusal gates, repeat idempotence and refusal of .20 after retirement.

The parent must serialize writers, recheck process isolation and sole ownership,
review canonical CHECK diff, converge and repeat, then verify functional
synchronized observation and known consumer reconciliation. Active service and
socket checks alone do not qualify observation or consumer continuity.

Preserve the durable ledger, held occupancy, immutable outbox and ambiguous
dispatch state. Do not blindly relaunch, release slots or rewrite wake payloads.
A completion first observed after its deadline can become a deadline outcome
without a result. Nonempty recovery is supported but has deadline/result risk;
neither lossless recovery nor guaranteed continuity is claimed.
If startup or observation fails, retain restart intent, backups and the ledger.
The parent owns bounded recovery; no implicit T3 downgrade or ordinary-current
switch is authorized by this source change.

The existing 32 Chaldea recovery tests passed job
`0947b43b-f561-4922-b30c-3966771f539b` at Chaldea `354206a`.
They are not repeated here. Fleet checks validate this inventory and render
change in isolated scratch, without controlling installed services.
