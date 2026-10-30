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
server, Movies library3 and dedicated catalog principal. It requests all three
holonet.read/holonet.curate/holonet.home scopes for the separately enrolled
chaldea-laptop-holonet-recommendations account. The credential path is
~/.config/chaldea/authentik/holonet-recommendations.app-password. It never reads
the ordinary catalog or retired session credential.

The signed namespace must be managed-recommendations, history empty, library
and catalog user unchanged, and actions exactly catalog.read, playlist.read,
playlist.manage, object.share, home.read, home.manage and object.delete.
Only a complete scope set is accepted, with no duplicates, extras or whitespace
aliases. The helper retains fixed HTTPS token/JWKS endpoints, no redirects,
RS256, bounded lifetime and foreign/unknown-claim refusal.

An exact independent recipient ceiling is needed without baking real user IDs
into every binary release. The one fixed public policy
/etc/webmcp-interactive/holonet-recommendations.json carries only version1,
owner "chaldea-fleet-config holonet recommendations", and 1..16 unique hex32
target_users. The helper verifies its FD-held no-follow custody: root-owned
nonwritable parents, root0644 single-link regular leaf, bounded bytes, strict
JSON. The signed target set must equal this cohort; ordering is immaterial.
There is no CLI path, target, scope or credential selector. The policy contains
no token, password, history or media. Existing Jocasta private enrollment is not
repurposed, and no broker, database, cache or daemon is added.

## Explicit fleet selection

Set webmcp_interactive_holonet_writer_enabled only in a reviewed operator
selection, with webmcp_interactive_holonet_writer_targets and a reviewed helper
artifact/pin that contains this mode. Defaults are false and an empty cohort;
no inventory selects them in this source. Keep webmcp_interactive_holonet_enabled
and holonet_catalog unchanged.

The role validates the cohort and separately delivered writer credential
metadata before writes. It never reads or checksums that app password. Existing
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
