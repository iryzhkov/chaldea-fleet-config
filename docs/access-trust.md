# Chaldea access trust

Source-only packaging. Fleet trust enrollment remains disabled. The issuer is
agent-a-2026-10; the new deployment anchor will be deployment-2026-10b, generated
by the orchestrator only on Normandy. No private key, signed bundle or host
action is part of this change.

## Publisher and renewal

**omarchy-normandy** is the always-on Omarchy/Arch x86_64 publisher, using
systemd-timesyncd. It runs no agent workloads. It replaces omarchy-pc, the gaming
PC, which is not always on. Homelab-infra's existing inventory host **normandy**
is a separate Debian application VM and retains its current roles.

The homelab-infra signer playbook installs a locked system UID
chaldea-publisher, no login or sudo, with 0700 home /var/lib/chaldea-publisher,
keys/ and state/. Root installs the program and its independent anchor config.
The new deployment key stays on Normandy and is never transferred. Its unique
SSH deploy key at keys/fleet-deploy-key is 0600 with write access to this
repository only. The updater on homelab has a different read-only deploy key.

The systemd publisher timer runs every 6 hours, with manual renewal through
systemctl start chaldea-publisher.service. Each run locks durable state, fetches
fleet main into a bare Git repository, takes a fresh healthy timesyncd sample,
and signs the next sequence with main's access-trust/issuer-grants.json.
The signer's durable SQLite high water and published sequence must both increase.
A separate durable verification state authenticates the envelope against the
root-installed pin before Git commit construction. Git plumbing changes only
access-trust/bundle.jws from the exact fetched parent. A final path/parent guard
precedes an ordinary fast-forward push. Repository code/hooks are never run.
Unhealthy clock, invalid signature, same/lower sequence, unrelated paths and
concurrent main changes stop publication. Previous confirmed public bytes remain.

Lifetime stays 24 hours. Six-hour renewal leaves 18 hours of tolerance after a
missed renewal. Publisher/Git loss adds no time to the signed expiry. An hourly
independent timer alerts when published_at is older than 12 hours or the bundle
is absent, once per stale episode. Failures emit one alert per failed invocation.
Both use existing feed post if available and usable by the publisher UID, else
journal only. No feed credential is introduced. The orchestrator records and
tests the actual route on Normandy before verifier activation.

The transport pins GitHub's public Ed25519 host key and uses BatchMode,
IdentitiesOnly, no agent, strict host checking and no operator SSH config.
A write deploy key can technically modify the whole repository if stolen;
the single-path guard is a program invariant, not a GitHub path restriction.
Root fleet configuration and repository write access remain part of the trust
base. Signature verification cannot defend against replacement of the root pin.

## Public pin flow and ordered deployment

Follow the exact ordered operator commands in
[homelab-infra's Normandy publisher runbook](https://github.com/iryzhkov/homelab-infra/blob/main/docs/normandy-publisher.md).
The orchestrator performs every host action and key creation:

1. Stage playbooks/chaldea-signer.yml only on omarchy-normandy, leaving timers off.
2. As chaldea-publisher, generate a NEW Ed25519 PKCS8 file with umask 077 and
   exclusive noclobber creation using openssl genpkey. Never reuse or transfer
   the retired omarchy-pc key. Extract only the public JWK using createPublicKey,
   and public SPKI DER SHA-256 using openssl pkey -pubout -outform DER.
3. Insert the public values in inventory/group_vars/all.yml here and
   homelab-infra vars/chaldea-runtime.yml. Set chaldea_deployment_anchor_kid to
   deployment-2026-10b, chaldea_deployment_anchor_public_jwk to {kty, crv, x},
   and chaldea_deployment_anchor_spki_sha256 to lowercase public SPKI digest.
   Keep chaldea_access_trust_anchors referencing those variables in both files.
   The source placeholders deliberately cannot pass activation checks.
4. Review and merge public pins in both repos, confirm CI and run infra's
   scripts/check-trust-pins.py FLEET INFRA. It compares runtime version/digest,
   canonical chaldea_access_paths, anchor flow and all public pin values,
   rejects placeholders and recomputes the SPKI digest from JWK.
   Akasha's /etc/akasha/config.json anchors come from the same resolved variable
   via infra roles/akasha/templates/config.json.j2. Publisher config is separate
   root-installed data, never derived from untrusted fetched main.
5. Generate the unique publisher SSH deploy key as that locked UID. Fetch only
   its public half to controller scratch and register with
   gh repo deploy-key add --allow-write -R iryzhkov/chaldea-fleet-config.
   Check repository rules permit this principal's guarded direct main push.
6. Explicitly initialize publisher.sqlite and verify.sqlite ONCE as the locked
   UID using the bundled access-maintenance initialize-state command. Never
   reinitialize existing state. Start the publisher service manually; it takes
   clock-health, signs and verifies, commits only the public envelope and pushes.
7. Inspect published kid/sequence/24h expiry, key/state ownership, actual alert
   route, second renewal and timer deadlines. Enable publisher and age timers
   only after the first push succeeds. Keep fleet enrollment false.
8. Once the new anchor is live, stop old publishing on omarchy-pc and delete
   the retired deployment-2026-10 key file after comparing its public fingerprint.
   Igor removes the retired anchor from his password manager. The new key stays
   solely on Normandy.

No tokens have verifiers yet, so this repin is safe before activation. Subsequent
anchor rotation with active verifiers needs explicit overlap and independent
pin deployment. The agent-a issuer key is unchanged and must not be regenerated.

## Verifier deployment and recovery

Homelab is managed by homelab-infra, never fleet-config. Continue its
[Akasha rollout](https://github.com/iryzhkov/homelab-infra/blob/main/docs/akasha-v1-deployment.md)
at step 4 only after publisher checks succeed. No broad fleet apply.

Pinned host-v0.2.0 supplies the maintenance and Akasha bundles, installed
root-owned under /opt/chaldea-host/releases/VERSION/host, with Node 26.10.0
at /opt/chaldea/node/bin/node. Runtime version/SHA-256 must match independently
in fleet and infra. Do not run source builds on the deployment host.

The canonical chaldea_access_paths map remains unchanged. Root updater state
is /var/lib/chaldea-access-trust/updater.sqlite, public envelope is
/var/lib/chaldea-access-trust-public/bundle.jws and clock evidence is
/run/chaldea-access-trust/clock-health.json. Public directories/files are
root-owned 0755/0644. Akasha's separate verifier state is
/var/lib/akasha/access-state.db, service-owned 0600 under a 0700 directory.
Bind directories read-only where isolation is used so atomic replacement remains
visible. Root clock timer runs every 10s; updater fetch runs every 120s.
Freshness is <=30s and the conservative clock offset bound is <=30s.
Homelab and agent-a retain timesyncd; chrony remains supported without migration.

Never share publisher, updater or verifier SQLite. Preserve high-water and key
history through restart; missing/corrupt state parks access. No automatic
initialization, rollback or old-state restore. Failed verification and fetch
preserve previous signed expiry. A failed/ambiguous push may have advanced the
remote, so fetch before diagnosis; the next publication exceeds both high waters.
The bare transport cache may be rebuilt with timers stopped. Durable state may
not be deleted to clear a failure.

Issuer rotation keeps explicit issue_until/verify_until ceilings and tombstones.
A higher-sequence empty-keys bundle revokes all issuers, published by an explicit
operator procedure. The renewal job refuses empty grants to prevent accidental
mass revocation. Ordinary disconnected issuer revocation can take the remaining
24h lease; 13-minute bearers plus skew retain the <15-minute cancellation bound.

## First issuer

agent-a-2026-10 is append-only, audience akasha, with exact source resources:

- daily-health / homelab / chaldea.daily-health.agent-a, report.
- fleet-timers / chaldea / agent-a.fleet, job_finished.
- toolfeedback / chaldea / agent-a.toolfeedback, tool_call.

The issuance window is 2026-10-17T00:00:00Z <= iat < 2026-11-16T00:00:00Z.
verify_until is 2026-11-16T00:13:30Z, exactly 810 seconds later. Rotate before
cutoff; never extend deadlines under an existing kid. This window is separate
from the 24h trust lease.

## Checks

Run tools/ci.sh through Chaldea with disk TMPDIR and scratch HOME. Infra's
scripts/test-chaldea-publisher.py tests real Git path/parent guards and synthetic
maintenance responses for increasing sequences, unhealthy clocks, verification
failure, failed pushes and deduplicated age alerts. Its check-mode inventory is
local and synthetic. Tests never SSH to Normandy/homelab or create private keys.
Source-only results are distinct from deployment and live timer verification.
