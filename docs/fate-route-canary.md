# FATE route canary, 2026-10-29

Igor approved the homelab publisher/Akasha validator and omarchy-pc reader, then
explicitly approved the existing Normandy signer publishing the two route scopes.
No other client is selected. The shared client default stays 0.4.11. Source
review and CI must pass before main merge, which can activate fleet pulls and
the existing six-hour trust publisher.

The PC-only inventory file selects reproduced client-v0.4.22 from Chaldea
a0412350. Exact archive SHA is in that file. Its route policy uses index 5,
unchanged quality floors, and explicit Sol/Opus baselines for reader and critical
roles. Sol high clears executor48/builder50; Sol medium does not. Quota admission
and pacing remain active. Reader transport is source-bound, and announceHost is
homelab so the PC never needs route append permission.

access-trust/issuer-grants.json adds only homelab route append and PC route read
ceilings, profile route-service/project chaldea/audience akasha. The matching
fate-route-helper-additions.json is an additive operator packet for the existing
root-owned helper configurations. Preserve all current helper fields and grants,
validate with the qualified client, and compare current bytes before replacement.
Do not rerun baseline enrollment over live Mission Control or quota additions.
No identity, issuer key, deployment anchor or signer state changes.

Deploy the compatible homelab Akasha packet from homelab-infra first. Trigger the
existing Normandy publication, verify its signed sequence and exact scope delta,
and run the existing trust updater on H/PC. Add only the two helper grants after
trust is current. Stage the verified root-owned publisher client and existing
Chaldea example units, with scores.formatVersion2 and the existing homelab-only
AA key. Verify a committed route_score_snapshot receipt before enabling PC reads.

On PC use pinned ansible-pull at the reviewed fleet commit, canonical site.yml
--tags chaldea_client. Review CHECK against exact prior versions/configs before
REAL, then repeat REAL and require changed=0, failed=0, unreachable=0. Preserve
the separate admitted exec wrapper and prior client releases. The ordinary user
waits service follows current and restarts onto 0.4.22; verify its health after REAL.
Read-only PC preflight found current and previous both at client-v0.4.11. Managed
old versions 0.4.0/0.4.2/0.4.7/0.4.8/0.4.20 are explicitly retained; 0.4.9 is absent.
Unversioned client directories are outside the role's managed cleanup pattern.
Recheck actual membership before applying rather than inferring release history.
Activation order matters: do not let the ordinary pull select the reader until
the protected snapshot path is ready. Root records any temporary timer hold and
restores its prior state within the same controlled canary.

Rollback disables the version2 producer before restoring older validator/client
pins and prior route.json. Preserve evidence, old releases, helper grants unrelated
to route, trust high water and all signing state. Reverting a scope requires a
new signed sequence, never a bundle/state rollback. Do not reset SQLite or lower
floors, clock or quota gates. Source tests and fixtures do not prove live access;
require real protected publication/read and native CLI recommendations.
