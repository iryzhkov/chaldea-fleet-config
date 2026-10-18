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
Publication metadata is not downloaded-package qualification. Require that
independent proof before any protected install or enablement.
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
