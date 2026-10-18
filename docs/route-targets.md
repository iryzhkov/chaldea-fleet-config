# FATE role targets and canonical delegation

FATE selects normal role targets. The maintained AGENTS.md/CLAUDE.md sources
and chaldea, review-delegation and roadmap-executor skills all require agents
to call `chaldea_route` or `chaldea route --role ROLE`, then pass the selected
`providerInstanceId`, `model` and `options` exactly to T3 `delegate_task`,
including effort. Explicit user overrides remain valid. Sonnet is excluded;
Haiku is allowed when selected. Maximum effort is high; only Luna/Haiku may
use available xhigh options. Never use max, ultra, ultrathink or ultracode.

Use `builder` for implementation and main diff reviews, `critical-review`
for consequential design or disputed findings, `bulk-read` for readers and
`general` for other work. Main other-provider reviews pass the writer's driver as
`authorProvider`, or CLI `--author-provider`. Route the independent peer under
the canonical review pair rule.
For a Codex author, main review normally starts with
`chaldea route --role builder --author-provider codex`.

A long-lived MCP may retain an old schema and reject new configuration keys.
Use the installed CLI with the same constraints before falling back. No T3
restart is required. A Codex builder pin may refuse a Codex author's review.
When FATE cannot recommend a target, the documented main-review fallback
uses live catalog IDs for Opus 5.5 medium on Claude or Sol 6.1 high on Codex,
always on the other provider. Record the fallback reason; do not retry the
pin indefinitely or silently select the author's provider. Before launch, compare
underlying provider drivers from the live catalog. Reject a same-provider target
unless the quota exception qualifies, even if FATE returned it despite the
requested author-provider constraint. Treat it as an unusable recommendation
and use the documented other-provider fallback. The chaldea skill
documents the other outage roles. Conserve Claude for required main reviews.

Follow [review-delegation](../roles/agent_config/files/skills/review-delegation/SKILL.md)
for review pairs, critical anchors and the quota exception. When quota is tight, pairs may
use two different models on one provider with fresh recorded quota evidence;
an actual stop is not required. One independent review is acceptable if the pair
cannot run. Unknown quota or collector HTTP 429 alone grants no waiver.
Exact-head acceptance and the two-fix-round limit remain unchanged.
FATE returns one target plus alternatives, not an automatic pair or effort optimizer.

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

On 2026-10-18, omarchy-pc alone had verified client-v0.4.2 installed.
Agent-a/agent-b user clients were not upgraded; laptop remained legacy.
The verified PC pins were Sol 6.1 high builder, Luna 6 medium bulk-read and
Sol 6.1 medium general, explicit operator fallback rather than AA qualification.
Native T3 supplied account-bound quota; the old HTTP collector was off.
Unknown/stale readings stay explicit. Scores, shared quota and automatic switching were off.
Source merge, release, installation and per-host verification are separate.
For dated evidence and subsequent status, see the
[Jocasta checkpoint](jocasta:5ad4f605ba5887e4e0c7c4dd207af6d4@326).
The parent owns merge/activation approval and reports guidance distribution and verification per host.
