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

Keep this PR draft and auto-merge off until the parent approves activation.
Merging main is deployment: active fleet pull timers converge awake hosts
within about four hours plus timer jitter, or on wake. Merge approval must
therefore include activation approval.
client-v0.4.0 is published from reviewed
Chaldea main 86ad10fa91891a3ffc76397212fdabff34cb014f, including merged #42,
#44, #45 and #46. Its downloaded archive and manifest both verify SHA-256
fc80729f9179340c7a29ff1eac5a310aea013ddb107633e4f9b2f1250691dc8d.
Only omarchy-pc receives this version/digest pin; other hosts retain v0.3.0.
The role refuses new reader/target keys on clients older than v0.4.0 before
writing files. No release was installed by publishing it.

The parent owns activation approval and the fleet-rollout procedure. For a
controlled one-host check/apply sequence, the parent must coordinate merge
timing with the pull service, or first obtain approval to pause the omarchy-pc
pull timer and wait for any active pull to finish. Do not merge first and
assume the next pull will wait for a manual check. This implementation thread
must neither merge nor arm auto-merge under its source-only authorization.

After approval, use only the chaldea_client tag with --limit omarchy-pc at the
accepted commit, first check, then apply, then a second apply with changed=0.
Resume a paused timer only within that approved procedure. The role upgrades
the current link and can restart quota and waits units; it does not restart
T3 or create credentials. Preserve the previous release and observer state.

Expected changes when main eventually converges:

| Host | Changes |
| --- | --- |
| omarchy-pc | Client v0.4.0, Codex role pins, enabled local Claude env-file reader in route and observer; quota/waits may restart. |
| agent-a, agent-b, laptop | Existing v0.3.0 and policies retained. Empty target/source overrides use the original route.json renderer, preserving bytes and avoiding formatting backups or restarts. |

The compatibility branch preserves existing rendered config on the three
other hosts. The bounded activation and validation target omarchy-pc only;
a later fleet release/policy rollout remains separate.

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
