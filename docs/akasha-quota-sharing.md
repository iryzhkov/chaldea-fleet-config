# Quota service sharing, disabled proposal

This milestone is separate from the accepted six-host feed/toolfeedback cutover.
Both new permission flags default false. docs/akasha-quota-ceilings.patch contains
only the two proposed signed ceilings and remains UNAPPLIED. It adds no live issuer ceiling, signer,
normal inventory activation or observer restart.

The laptop UID1001 may append only quota_headroom_snapshot to source quota,
profile quota-service, project chaldea, exact canonical laptop host. PC UID1000
may read only that service projection with quota_fleet_read=true. This is not
global_read and does not grant PC quota append. Other hosts gain neither permission.
Existing feed/toolfeedback, daily-health RunLease and seven PC native kinds stay
unchanged. Existing signer validity through Nov16 and token lifetime <=780s apply.

Use the existing one-host enrollment wrapper with these additional public inputs:
akasha_quota_laptop_publisher_enabled and akasha_quota_pc_reader_enabled.
Both must be booleans. Runtime pins are fixed in the explicit play, not public
input overrides: client-v0.4.2, SHA256
40a00e518152f1d44251dc1bffddcea34ca613f43453a7dbf26ec890247c539a,
published from reviewed green main9d434 by workflow39120608965. The manifest API
SHA is80d1300524ae52e789388fd72cdc774058ed019247debf34d5bf2840066a4d45.
Actual downloaded-package qualification passed agent-a job
 a933ef74-57d8-4687-b747-19b9aa733c37: all3168files/178source match9d434,
actual CLI/account/isolation proof passed. This is source evidence, not approval
for protected installation or quota activation before joint source acceptance.
Stage the exact protected quota archive and manifest under /opt/chaldea-token-helper
using the canonical quota-runtime task subset before a meaningful enabled check.
The early read-only canonical verifier refuses missing/mismatched artifacts before
helper or collector effects. Its check does not install the release.

The canonical installer installs only a new immutable protected version, alongside
private helper0.4.0. It never changes current/previous, helper launchers, normal
user-client pins or retention. Normal client_enabled=true applies to laptop too.
Its normal observer remains disabled and its canonical unit/config remain owned by
normal fleet pulls. The explicit sharing play uses only task-scoped runtime flags
to render fixed chaldea-quota-sharing.service and quota-sharing.json.

The laptop service uses its actual existing local T3 base and read-token path,
user Node26.10, isolated XDG config/state, its own observer/cache/journal and
/usr/bin/true feed command. The private isolated events.json is empty and restart
is disabled. No provider switching, session control or native chaldea-quota append
is authorized. Before activation the normal observer must be inactive/disabled;
never run two quota publishers. Keep local tokens in custody.

PC gets only quota-fleet-reader.json, preserving normal account contexts. The
actual observer quota.json must have fleet absent/disabled and normal unit args.
The unapplied akasha-quota-sharing-inventory.patch persists the fixed reader path
through existing route_targets.quotaConfigFile. Activation refuses without that
main-source agreement. A narrow routing-file update changes only that field;
normal fleet pulls then render the same choice. It does not restart PC's observer.

Publication is one combined snapshot per 15-minute bucket, at most4/hour, using
the existing persistent reservation. Readers request verified last15-minute data.
The native-only laptop configuration binds Claude only and omits unbound Codex.
The actual CLI fixture f35913d5 proves bound Claude weekly69, credits:null and
explicit resets0, unbound Claude/Codex omitted, zero native appends/session changes,
and unchanged normal config. Codex absence preserves PC wallet60149.468211;
mergeSnapshots chooses the whole newest account, not a general richer local merge.

Before activation: qualify the green-main0.4.2 release/archive/manifest/native
account bindings; complete one joint cross-provider review of final fleet+infra
heads; compare the exact adapter render and infra registry; review and merge only
the exact two public issuer ceilings through the existing publisher workflow;
verify the new signed bundle/healthy clocks; persist the PC reader path in main.
Only then use the pinned current-main activation wrapper on the exact laptop/PC
accounts, inspect check diff, apply and require a second REAL changed=0. Confirm
actual PC observer has no fleet publication, router reads the separate file,
laptop emits only source quota, native/account hashes and freshness match, and
there are zero denied/unintended appends or session mutations. No broker, extra
signer, token copying, helper migration or replacement UI is part of this work.

## Exact future laptop archive staging

These are proposed operator commands after joint source acceptance and parent
release of quota installation scope. They are not run by this source change.
Use only the laptop igor UID1001, existing protected bootstrap layout and the
exact accepted main checkout. They stage public files only, without installing
a runtime tree, minting, creating keys or enabling services. The following
canonical verifier CHECK in the enrollment play then has real cached inputs.

```sh
set -eu
test "$(hostname --short)" = omarchy-macbook-air-igor
test "$(id -u)" = 1001
test "$HOME" = /home/igor
test "$(git rev-parse HEAD)" = "${REVIEWED_MAIN_SHA:?exact merged source pin}"
export TMPDIR="$HOME/.cache/chaldea-scratch/akasha-quota-sharing-20261018"
mkdir -p "$TMPDIR"
sudo test -d /opt/chaldea-token-helper/releases
sudo test ! -L /opt/chaldea-token-helper/quota-client-v0.4.2.tar.gz
sudo test ! -L /opt/chaldea-token-helper/quota-client-v0.4.2.json
if ! sudo test -e /opt/chaldea-token-helper/quota-client-v0.4.2.tar.gz; then
  sudo curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 120 \
    https://github.com/iryzhkov/chaldea/releases/download/client-v0.4.2/chaldea-client.tar.gz \
    --output /opt/chaldea-token-helper/quota-client-v0.4.2.tar.gz
fi
printf '%s  %s\n' 40a00e518152f1d44251dc1bffddcea34ca613f43453a7dbf26ec890247c539a /opt/chaldea-token-helper/quota-client-v0.4.2.tar.gz | sudo sha256sum --check -
if ! sudo test -e /opt/chaldea-token-helper/quota-client-v0.4.2.json; then
  sudo curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 120 \
    https://github.com/iryzhkov/chaldea/releases/download/client-v0.4.2/manifest.json \
    --output /opt/chaldea-token-helper/quota-client-v0.4.2.json
fi
printf '%s  %s\n' 80d1300524ae52e789388fd72cdc774058ed019247debf34d5bf2840066a4d45 /opt/chaldea-token-helper/quota-client-v0.4.2.json | sudo sha256sum --check -
sudo chmod 0600 /opt/chaldea-token-helper/quota-client-v0.4.2.tar.gz /opt/chaldea-token-helper/quota-client-v0.4.2.json
```

Refuse an existing mismatched file rather than replacing it. Continue with the
existing explicit laptop enrollment wrapper in stage --check mode and the exact
approved public input file. Its canonical quota-runtime CHECK verifies both
archive and immutable-tree state without installation. The later accepted
activation invokes the same role subset for the actual immutable install.
