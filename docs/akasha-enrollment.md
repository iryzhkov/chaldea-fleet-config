# Explicit Akasha enrollment, source preparation

This play reuses the canonical fleet installers once on six named hosts. It never
runs site.yml, installs a fleet pull timer or changes provider/Huyang/user-client
configuration. Normal fleet inventory and role bytes are unchanged. Infra still
owns the Akasha server, edges, trust publisher and homelab/Normandy trust settings.

All enrollment and optional permission toggles default off. No production public
keys are supplied. No deployment, key creation, grants, merge or live checks were
performed by this source preparation. CLI-only feed and eventual old browser UI
retirement are accepted; no replacement UI is needed.

## Required operator inputs

After explicit credential/host-scope approval, provision the five host-local
signers and reuse agent-a as recorded in the operator packet. Preserve its
daily-health RunLease, source IDs and original ceilings. Do not create/rotate the
Normandy deployment anchor. Initialize only genuinely absent issuer state.

Preflight requires the independently verified client-v0.4.0 archive tree staged
at /opt/chaldea-token-helper/releases/client-v0.4.0, its pinned root-owned Node
26.12.0, the pinned archive/manifest retained beside it, operator-provisioned trust
transport and durable state, and the Node 26.10.0 collector/trust runtimes.
Fleet trust outputs may be absent at stage. Activation invokes trust first and
checks its generated outputs before enabling a collector. Infra-owned outputs
must already exist on homelab/Normandy, including Normandy consumer trust from
infra playbooks/akasha-normandy-consumer-trust.yml, disabled by default. Stage that public validation runtime through the existing
library/chaldea_client_release.py verifier and reviewed Node checksum inputs.
This play deliberately fails before installation if the validation prerequisite
is absent. It does not bootstrap past its own validation or upgrade the FATE user
client. No new package/distribution mechanism is added.

The public input JSON has exactly akasha_enrollment_public_keys, with a public
Ed25519 JWK for each canonical inventory name. Optional boolean fields
akasha_pc_global_reader_enabled and akasha_pc_quota_events_enabled default false.
Only set them after separate approval. The reader exposes every native kind to
PC UID 1000 and same-UID processes; helper kind selectors do not narrow that read.
The quota proposal is seven exact PC append kinds, excluding provider switching.
When explicitly approved, activation writes only PC events.json and restarts its
existing quota user service if that file changes. It does not upgrade its client.
The thin composition adapter imports publicKey, validateBundle, helperConfig and
Authorization from the verified client. It adds no JWK/ceiling validator.

The adapter's stdout contains public native issuers, grants and additive registry
records. Save a reviewed render to private operator scratch. Existing infra
vars/akasha-registry.yml entries must be retained and the additive registry rows
merged through the existing Akasha play's input. Existing issuer-grants.json
records are retained in issuers. Final public manifest commits await real keys
and review; the absent-key source is intentionally not a finalized live manifest.

## Pinned, local invocation after approval

Use an already-reviewed checkout to invoke the guard, as the exact producer user:

    python3 tools/akasha-enrollment-pull.py CANONICAL_HOST EXACT_40_HEX_SHA /absolute/public-inputs.json stage --check

The guard accepts one literal host, no Ansible passthrough arguments, and checks
local hostname/UID/home before ansible-pull. It pulls that exact SHA into a
separate cache and runs only playbooks/akasha-enrollment.yml with a literal limit.
Laptop is omarchy-macbook-air-igor and Normandy is omarchy-normandy, not the normal
fleet aliases. The pinned ansible-core-2.19.14 executable must already exist.

Before fleet activation, the normal inventory must explicitly persist matching
akasha_collector_enabled=true, URL and helper on the four approved host entries.
The play refuses activation without those three values because the next ordinary
pull would otherwise disable the collector again. This source PR deliberately
keeps those inventory outputs unchanged. That later 12-value activation delta
is supplied as the reviewable docs/akasha-activation-inventory.patch, without
applying it. It belongs to parent integration only inside the authorized cutover
window, after keys, trust, ingress/import and all user/system/cron shipper gates
are ready. The activation pin must be that current main commit, not a branch-only
commit; the local guard verifies main before activation. Do not merge the patch
early, because ordinary pulls could then activate collectors automatically.

After inspecting check diff, repeat without --check. Stage installs helper grants
and disabled collector files; it can admit helper minting if signed trust is
already active, so stage itself needs credential approval. It refuses an already
active/enabled collector rather than disabling it. It does not activate trust.
Before activate, publish the reviewed issuer ceilings using the existing
Normandy-only publisher, apply retained-plus-additive infra registrations, verify
current trust/clock and complete the packet's ingress/import/retirement gates.
Stop the exact obsolete toolfeedback user shipper units first, keeping their
spools/state. Activation rejects a running old shipper. It never stops unrelated
jobs or changes pull/retention schedules. Then use activate --check, inspected
activate, second activate changed=0 and functional verification. Trust role
invocation is activation-only on four fleet hosts; infra trust is consumed intact.
Feed configuration has one owner: this play on four fleet hosts, infra drift_check
on homelab/Normandy. Infra writes no off-PC reader label and retains config backups.
The user-unit guard does not replace exact system-unit/cron/hook inventory; those
remaining shipper gates and cold-host commands are in the operator packet.

No UI parity or live proof is claimed. Retain old feedd data, consistent snapshot,
old immutable release/config and credentials, local transcripts/spools and
archival Loki reads. Retire replaced services/UI/token-URL docs/install paths only
after verified cutover, with no extra retirement confirmation.
