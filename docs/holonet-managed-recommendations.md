# Ordinary native HoloNet recommendation capability

This source is default-off. It provides no live account, writer grant, recipient
selection, deployed helper pin or service activation. The catalog reader keeps
its own credential, registration and unchanged signed contract.

The separate registration name is holonet_recommendations, limited to ordinary
Claude/Codex on laptop. Its only helper command is
/usr/local/libexec/webmcp-interactive-headers holonet-writer laptop.
It neither selects OpenCode nor restores any retired limited provider or waits
profile. The actual node must be omarchy-macbook-air-igor and UID1001.

## Fixed identity and exact cohort

The helper uses the existing chaldea-holonet issuer/client/resource and fixed
server, Movies library3 (or the policy's explicit library_ids below) and
dedicated catalog principal. It requests all three
holonet.read/holonet.curate/holonet.home scopes for the separately enrolled
chaldea-laptop-holonet-recommendations account. The credential path is
~/.config/chaldea/authentik/holonet-recommendations.app-password. It never reads
the ordinary catalog or retired session credential.

The signed namespace must be managed-recommendations, library and catalog user
unchanged, and actions exactly catalog.read, playlist.read, playlist.manage,
object.share, home.read, home.manage and object.delete. History is empty unless
the public policy below opts in to scoped playback history; then the actions
are exactly those seven followed by history.read, and the signed
holonet_history_users set must equal the policy's history_users set. The
ordinary catalog reader always requires empty history and catalog.read only.
Only a complete scope set is accepted, with no duplicates, extras or whitespace
aliases. The helper retains fixed HTTPS token/JWKS endpoints, no redirects,
RS256, bounded lifetime and foreign/unknown-claim refusal.

An exact independent recipient ceiling is needed without baking real user IDs
into every binary release. The one fixed public policy
/etc/webmcp-interactive/holonet-recommendations.json carries only version1,
owner "chaldea-fleet-config holonet recommendations", and 1..16 unique hex32
target_users, plus two optional fields, history_users and library_ids. The
helper verifies its
FD-held no-follow custody: root-owned nonwritable parents, root0644 single-link
regular leaf, bounded bytes, strict JSON. The signed target set must equal this
cohort; ordering is immaterial.

history_users, when present, must be a JSON array of unique IDs drawn from
target_users. Absent or empty keeps the original writer contract. A nonempty
set admits a token only when its signed history set equals the policy set,
with no duplicates, foreign IDs, aliases, wildcards or extras; ordering is
immaterial. History authority is never derived from the target cohort, and no
scope, account, credential or request field changes. There is no CLI path,
target, history, scope or credential selector. The policy contains no token,
password, viewing data or media. Existing Jocasta private enrollment is not
repurposed, and no broker, database, cache or daemon is added.

library_ids, when present, must be a JSON array of 1..3 unique canonical
decimal strings (no sign, leading zero, zero, whitespace or number type) that
includes "3". Absent keeps the original Movies-only writer, which requires the
signed holonet_libraries to be exactly ["3"]; a supplied empty array, null or
any other type refuses. A present set admits a token only when its signed
holonet_libraries set equals the policy set, ordering immaterial, with no
duplicates, foreign, missing or extra IDs. The policy is the allowlist: the
helper hardcodes no TV or anime library. The Movie/TV/anime opt-in is
["3", "615", "1132"]. Libraries change no action, history, target, scope,
account, credential or request field, and the ordinary catalog reader keeps
exact library3, catalog.read and empty history.

## Explicit fleet selection

Set webmcp_interactive_holonet_writer_enabled only in a reviewed operator
selection, with webmcp_interactive_holonet_writer_targets and a reviewed helper
artifact/pin that contains this mode. Defaults are false and an empty cohort.
The laptop inventory selects the existing writer with its seven recipients,
scoped playback history, and explicit Movies3/Anime615/TV1132 library grant.
The ordinary catalog reader remains Movies3-only. The selected ARM64 helper
145463c7 is built from8bba68c in Chaldea4147b212. Merge this candidate activation
only after guarded helper installation, matching issuer writer grant and
native qualification; source selection alone is not installed-state evidence. The ordinary reader selection and
holonet_catalog remain unchanged.

webmcp_interactive_holonet_writer_history_users defaults to empty and is set
only in the same reviewed selection, as an explicit subset of the targets. The
role renders history_users only when it is nonempty, so the default policy
bytes are byte-identical to the earlier source. Opting in, and rolling back to
empty, each replace the existing policy only through the previous-policy digest
below. A helper release that predates history_users refuses a policy carrying
it, so install the reviewed helper before rendering a nonempty history.

webmcp_interactive_holonet_writer_library_ids likewise defaults to empty, which
omits library_ids and keeps the default bytes. Otherwise it must be 2..3 unique
canonical decimal strings including "3"; the role refuses ["3"] alone, since
that equals the default and would only change bytes. The role validates it
before any stat or write and renders it sorted. Opting in and rolling back use
the same previous-policy digest. A helper release that predates library_ids
refuses a policy carrying it, so install the reviewed helper first, and enroll
the matching issuer writer grant before rendering the set.

The role validates the cohort, history subset and separately delivered writer
credential metadata before writes. It never reads or checksums that app password. Existing
public policy paths must have exact root custody; only current desired bytes or
an explicitly supplied webmcp_interactive_holonet_writer_previous_policy_sha256
permit replacement. Foreign content or unsafe paths refuse. The policy is
written atomically through the maintained copy module and has no backup.

The existing owned native registration inverse is state=absent for the exact
holonet_recommendations entry while the selection/custody inputs are still
available. A false flag alone is not a retirement operation and is not claimed
to revoke cached tokens. Retain the public policy and issuer credential until
their separate owned retirement is prepared. Existing reader and unrelated
registration values remain preserved; the shared TOML serializer may retain
a trailing newline after an inverse.

## Remaining activation gates

The maintained issuer generic writer tuple and strict service installer were
merged separately in homelab-infra PR106. They do not enroll this identity or
supply backend permissions. Prepare one concrete packet with the named cohort,
public-policy digest, issuer account/subject/grant, service subject/target
intersection, baseline/anchor ownership and least backend permission. Preserve
the catalog identity, auth assets, sole waits and protected OpenCode. Source
reviews and CI, exact binary/host convergence, owned inverse, bounded live canary,
real native authentication and useful web/TV presentation remain separate gates.

Synthetic signed-token/helper and native-config/Ansible tests are source proof.
They do not establish current production token issuance, non-root laptop
execution, connection continuity, renewal, viewing history, recommendation
quality, rendering or a live write. No recurring policy is enabled.
