# FATE role targets and canonical delegation

FATE selects normal role targets. The maintained AGENTS.md/CLAUDE.md sources
and chaldea, review-delegation and roadmap-executor skills all require agents
to call `chaldea_route` or `chaldea route --role ROLE`, then pass the selected
`providerInstanceId`, `model` and `options` exactly to T3 `delegate_task`,
including effort. Explicit user overrides remain valid. Sonnet is excluded;
Haiku is allowed when selected. Never use max effort or above.

Use `builder` for implementation and main diff reviews, `critical-review`
for consequential design or disputed findings, `bulk-read` for readers and
`general` for other work. Reviews pass the writer's driver as
`authorProvider`, or CLI `--author-provider`, to require the other provider.
For a Codex author, main review normally starts with
`chaldea route --role builder --author-provider codex`.

A long-lived MCP may retain an old schema and reject new configuration keys.
Use the installed CLI with the same constraints before falling back. No T3
restart is required. A Codex builder pin may refuse a Codex author's review.
When FATE cannot recommend a target, the documented main-review fallback
uses live catalog IDs for Opus 5.5 high on Claude or Sol 6.1 high on Codex,
always on the other provider. Record the fallback reason; do not retry the
pin indefinitely or silently select the author's provider. Before launch, compare
underlying provider drivers from the live catalog. Reject a same-provider target
unless the quota exception qualifies, even if FATE returned it despite the
requested author-provider constraint. Treat it as an unusable recommendation
and use the documented other-provider fallback. The chaldea skill
documents the other outage roles. Conserve Claude for required main reviews.

Only an observed other-provider quota stop with a reliable reset more than
one hour away permits the explicit review-delegation quota exception.
Unknown windows/reset or collector HTTP 429 alone do not qualify. A qualifying
Sol-authored review uses a fresh stronger reviewer, preferably Astra high,
with the stop/reset evidence, waiver reason and exact-commit verdict recorded.
Exact-head acceptance and the two-fix-round limit remain unchanged.

## Configuration support

A compatible role-target client accepts `chaldea_client_route_targets`.
Empty overrides preserve older clients' route.json bytes. Keys override the
template's base values; use only documented client fields. PR 52 already
provides the target plumbing, compatibility renderer and version guard.

Pins require an available catalog model, allowed effort, provider separation
and quota admission. Supported policy fields include pins, bans, floors,
probation and score settings. AA support is not a claim of live activation.
The AA key stays only on homelab. Future shared score snapshots contain no
secret and require compatible Akasha registrations and scoped grants. Never
put the key in inventory, prompts or this repository. Missing coding metrics
stay unknown; floors are never rounded up or lowered to admit candidates.

## Verified activation boundary

The 2026-10-18 rollout installed client-v0.4.0 on omarchy-pc only at da518de.
Merged PR 52 has identical runtime/inventory bytes. Its explicit conservative
pins select Codex Sol 6.1 high for builder, Luna 6 medium for bulk-read and
Sol 6.1 medium for general. These are fallback pins, not AA qualification.
Other hosts retain client-v0.3.0 and have no new role-target verification.

The local Claude reader is approved, enabled and attempted on omarchy-pc only.
Route and quota use its existing 0600 env file without copying or refreshing
credentials. The collector's 429/backoff is not a fresh quota measurement.
Read cached status and honor retryAt. Do not claim all logged-in hosts have
live readers. AA snapshots, shared quota and automatic switching remain off.

The source PR stays draft with auto-merge off. Active pull timers distribute
merged guidance, so the parent owns merge/activation approval and must report
AGENTS.md/CLAUDE.md and skill distribution and verification per host. Source
and review preparation alone do not complete the plan30 gate.
