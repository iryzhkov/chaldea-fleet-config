# Per-host identity cutover

This is preparation for M3 P3.1 step 3. No host inventory enables the switch.
Base: main 72add22. Survey: jocasta:bb2fc17fa5ceaa265efbdb7c4c3d9ac0@1.
The authoring guide was read at revision 45.

The native Claude headersHelper, Codex http_headers_helper and OpenCode plugin
keep their existing commands and configuration bytes. Each invocation checks
the root-owned public selector /etc/webmcp-interactive/host-identity-HOST.
Absence keeps the old identity. Its exact content selects chaldea-HOST and
the account database home plus .config/chaldea/authentik/host.app-password.
The credential is read with the existing no-follow, owner, 0600, single-link,
private-parent and bounded-content guards. A selected missing or unsafe
credential refuses before network access, with no old-identity fallback.
No token is cached. Resource, issuer, scope, audience, signed-claim validation
and individual HoloNet purpose requests keep their existing contracts.

Fleet checks host credential metadata only. It neither delivers that password
nor copies it into enrollment.json. Existing enrollment copies, profile
launchers and old credentials remain for rollback. Akasha, token-helper, PKI
and deleted M1 profile inputs are outside this change.

## Cutover owned by the root

1. Finish issuer admission and consumer coexistence first. Enroll the owned
   chaldea-HOST identity beside the old identity and deliver its private host
   credential through homelab-infra. Preserve the exact survey grant matrix.
   OV personal subject admission and both HoloNet Go and root-worker subject
   policies must accept the new subject before switching those hosts. Finish
   or explicitly abandon old pending HoloNet operations without reassigning
   their ownership.
2. Publish and pin the reviewed helper artifact for each host. Update the owning
   host helper hash/source with the normal guarded upgrade receipt. Coordinate
   active pull writers and preserve the installed rollback artifact.
3. In that host's vars set chaldea_host_identity_enabled: true. Switch agent-b
   first, then agent-a, omarchy-pc and laptop, accepting each before the next.
   Homelab follows its separately owned operator play; this helper does not add
   HA/observer or new homelab registrations. Normandy stays outside P3.1.
4. Read the complete selected CHECK diff. After root approval, trigger one
   controlled pull on the target:
   systemctl --user start chaldea-fleet-pull.service
   Capture its real exit/outcome and repeat for zero changes. Confirm exact
   helper and selector custody and host credential metadata without exposing,
   copying or hashing secrets. Check timer health.
5. Use actual native Claude and Codex connections for every selected resource.
   Agent-a/b must exercise Jocasta operator read/write using disposable
   documents, CAS, idempotency and stale refusal. omarchy-pc additionally checks
   OV resource actions and separately signed default/default personal actions,
   and Shizune owner igor/use. Laptop additionally checks Movies-only catalog,
   writer libraries 3/615/1132 with exact target/history users and independent
   importer/custody, torrent and seed-join read purposes. Optional acquisition
   support does not authorize enabling new grants. Check OpenCode separately
   wherever selected. Record public issuer/audience/subject/scope/claim evidence
   and actual native traces, never bearer values or passwords.
6. Run negative cases through owned fixtures: ungranted agent OV/HoloNet access,
   wrong issuer/audience, cross-resource replay, foreign resource claims,
   missing/wrong scope, combined HoloNet purposes, expanded namespaces,
   libraries, recipients or actions, and API-rotation bearer refusal. Limited
   Jocasta tokens must still fail writes. Missing/unreadable host credentials
   must fail before token issuance without fallback. Do not remove or chmod a
   real credential to test this; use isolated fixtures. Verify post-token-
   lifetime access separately without claiming observed rotation.
7. Record acceptance per host. Keep a bounded coexistence/rollback window.
   Removing old subjects/accounts, credentials and launchers is P3.1 step 4.

## Rollback

Set chaldea_host_identity_enabled: false in only the affected host's vars and
run the same controlled pull. Fleet removes its public selector and resumes
the preserved old enrollment and resource-specific credentials. Keep the new
host credential in place for investigation; do not revoke old identity inputs
during the rollback window. Confirm zero-change repeat, native resource
access, unchanged unrelated registrations and pull timer health. If reverting
the helper artifact itself, first remove the selector through the new role,
then use the retained reviewed artifact and normal hash custody guards.
