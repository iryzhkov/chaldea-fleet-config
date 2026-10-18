# Conservative routing and native Claude quota

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

PC normal Claude/T3 now supplies native quota. client-v0.4.2 binds it to the
instance's validated account hash; normal Claude/T3 owns credential renewal.
Pair this pin with PR 57, which disables the redundant route/observer HTTP
collectors while preserving the existing private oauth.env file. Stale or
unsupported observations remain explicit; a collector 429 is not fresh quota.
Shared Akasha publishing, AA adaptation and provider switching remain off.

## Activation boundary

Keep this PR draft and auto-merge off until the parent approves activation.
Merging main makes the pin eligible for active fleet pull timers, which may
converge awake hosts within four hours plus jitter, or on wake. Merge approval
must include activation approval; report installation only after verification.
client-v0.4.2 is published from reviewed green Chaldea main
9d4341953e20f71c023e8fabbb0c7eba0542aaf5. Its downloaded archive verifies SHA-256
40a00e518152f1d44251dc1bffddcea34ca613f43453a7dbf26ec890247c539a;
manifest.json has SHA-256 80d1300524ae52e789388fd72cdc774058ed019247debf34d5bf2840066a4d45.
Only omarchy-pc receives the proposed version/digest pin; other hosts retain v0.3.0.
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
| omarchy-pc | Client v0.4.2, existing Codex pins; paired PR 57 uses bound native Claude quota with HTTP readers off. |
| agent-a, agent-b, laptop | Existing v0.3.0 and policies retained. Empty target/source overrides use the original route.json renderer, preserving bytes and avoiding formatting backups or restarts. |

The compatibility branch preserves existing rendered config on the three
other hosts. The bounded activation and validation target omarchy-pc only;
a later fleet release/policy rollout remains separate.

After activation:
1. Confirm current resolves to the pinned immutable release.
2. After the paired config converges, confirm all three Codex pins remain,
   route claudeUsage is disabled and quota.json has no HTTP Claude context.
   Inspect selected fields; preserve the private legacy env file.
3. Run the installed chaldea route for the three roles. Verify Codex targets,
   correct efforts and explicit fallback reasons. A builder review with
   --author-provider codex must refuse its Codex pin; critical-review must use Claude or refuse.
4. Use installed chaldea quota status --json after natural observation.
   Verify fresh matching-account Claude windows from T3 without the old HTTP
   429 attached; unsupported/stale data stay explicit and Codex credits remain intact.
5. Verify no cross-host snapshot publishing, new credentials, AA fetch service,
   or provider switch was enabled. AA source corrections and fleet rollout
   remain separate. Update canonical delegation guidance once the live
   FATE checks pass, preserving the pending quota-exception guidance change.

Use the qualified immutable release for verification. Source/package success
is separate from parent-approved installation and per-host verification.
