# Conservative routing and local Claude reader

Igor's 2026-10-18 budget policy uses existing FATE role pins on omarchy-pc:
builder Sol 6.1 high, bulk-read Luna 6 medium, general Sol 6.1 medium.
These are explicit operator fallback choices, without an AA quality claim.
AA adaptation is unavailable pending the missing coding metrics and strict
below-floor anchors. Floors, score mappings and probation are unchanged.
A pin excludes other models/providers; Codex unavailability refuses the role
instead of spilling builders or readers to Claude. Explicit caller model
overrides remain possible. Critical review stays unpinned and must pass
authorProvider to preserve the different-provider rule. The plan r31 known
quota-stop/reset-over-one-hour review exception remains an explicit session
decision, never inferred from unknown quota.

The local Claude usage reader is already approved by plan r31. Both route
claudeUsage and observer claudeContexts bind claudeAgent to the same existing
0600 oauth.env and only CLAUDE_CODE_OAUTH_TOKEN. T3's installed user service
uses that exact EnvironmentFile. No credential is copied into inventory,
logs, argv or source, and collection never refreshes OAuth. Account identity
comes from provider responses. Shared Akasha publishing stays disabled;
local collection requires neither grants nor dashboard/AA activation.

## Activation boundary

This PR is source preparation only. Before activation, publish the reviewed
Chaldea main client containing merged #42, #44, #45 and #46 as client-v0.4.0.
Verify its release archive and manifest, then pin version and exact archive
SHA-256 for omarchy-pc only. Do not apply these new config keys to v0.3.0.
The compatible pin is a merge prerequisite for this PR.

The parent owns the bounded one-host activation approval and fleet-rollout
procedure. Use only the chaldea_client tag with --limit omarchy-pc at the
accepted fleet-config commit, first check, then apply, then a second apply
with changed=0. This role upgrades the current link and can restart its quota
and waits units. It does not restart T3 or create credentials. Preserve the
previous release and observer state for rollback.

After activation:
1. Confirm current resolves to the pinned immutable release.
2. Confirm route.json has all three Codex pins and the envFile binding;
   quota.json has the matching enabled Claude context. Inspect selected keys,
   never the env file contents.
3. Run the installed chaldea route for the three roles. Verify Codex targets,
   correct efforts, and explicit pin/fallback reasons. For review pass
   --role critical-review --author-provider codex and verify Claude or refusal.
4. Let the already configured observer collect, then use installed
   chaldea quota status --json. Verify a fresh Claude weekly and short window,
   or its sanitized failure/backoff reason with last-good age. A 429 is
   rate_limited, not a successful quota measurement; honour retryAt.
5. Verify no cross-host snapshot publishing, new credentials, AA fetch service,
   or provider switch was enabled. AA source corrections and fleet rollout
   remain separate. Update canonical delegation guidance once the live
   FATE checks pass, preserving the pending quota-exception guidance change.

The old installed client has no safe env-file reader command, so do not run
new checkout source against real credentials to obtain a preliminary reading.
The reviewed release and binding are the actual prerequisites, not approval.
