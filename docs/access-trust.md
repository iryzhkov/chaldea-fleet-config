# Chaldea access trust (package F, trust slice)

Source-only packaging. Inventory is disabled everywhere; grants are empty.
No signed bundle, real keys or host changes are included. Run-profile UID, T3,
proxy and nft work remains separate. Authority: chaldea docs/access-v1.md at
76aecaa plus PR #10's 24h age, and
jocasta:14ce7ddae80badf228ca6ef0779e3f2e@1 sections 2/6 package F.
Homelab-infra PR #11's old 600s maximum age is superseded by **86400s**.
Its 120s fetch and healthy clock offset <=30s requirements remain.

## Static publisher choice

Reuse this private GitHub repository. access-trust/issuer-grants.json contains
operator-reviewed public keys/ceilings; access-trust/bundle.jws will contain only
the operator-signed compact envelope. No new listener or publication credential
on a run host. Hosts already use read-only per-repository deploy credentials for
ansible-pull; this root updater gets its own read-only key for the same scope.
The existing 4h ansible-pull timer is too slow, so fetch is independent.

Git-over-SSH pins the transport host key, then package C verifies a separate,
independently pinned Ed25519 deployment anchor. The bare cache never checks out
or executes repository code. Only bundle.jws goes to the installer.

Requests use local cached trust. Any single fleet host may be down without an
online trust dependency for others. Publisher/Git loss is tolerated until the
existing signed expiry, at most 24h after publication. It does not add a day at
outage detection. Renew well inside the lease and alert before expiry.
Disconnected issuer-key revocation can take the remaining 24h lease; bearer
expiry and ordinary cancellation retain their <15m bound.

## Future deployment procedure (not performed; requires rollout approval)

Host list: **omarchy-pc** holds the deployment anchor and publishes; **homelab**
runs Akasha's verifier updater and clock adapter. **agent-a** is the first future
issuer and needs its own key, clock and trust state before minting. agent-b,
laptop, normandy and public-api/public-api-b have no action in this slice.
Later enrollment needs an explicit host list. No broad fleet apply.

1. Freeze reviewed application/fleet commits and successful CI. Separately install
   immutable chaldea source under root-owned /opt/chaldea/app and pinned Node
   26.10.0 at /opt/chaldea/node/bin/node on homelab (later agent-a).
   ProtectHome requires runtime outside /home. Provision git, openssh-client,
   python3 and chrony through approved host configuration. Require independent
   external time sources and the root-protected /run/chrony/chronyd.sock socket;
   no UDP fallback, chrony local/orphan mode or single fleet NTP host.
   This role does not install or change time services.
2. Igor, as igor on **omarchy-pc only**, creates
   /home/igor/.local/share/chaldea-access-publisher/keys (owner igor, 0700).
   With umask 077, run openssl genpkey -algorithm ED25519 -out
   <keys-dir>/deployment-2026-10.pem. The PKCS8 file is igor-owned 0600,
   single-link. Protect ancestors. Igor holds its protected offline backup;
   omarchy-pc holds the sole live deployment key. Never copy it to a run host,
   sandbox, repository, env or transcript. Independently compare its public
   fingerprint/JWK before pinning chaldea_access_trust_anchors in approved
   inventory and Akasha config.
3. For each approved issuer (first agent-a), the operator separately provisions
   locked service identity chaldea-issuer, distinct from the run UID, without
   login, sudo or operator groups. Create /var/lib/chaldea-issuer/keys and
   /var/lib/chaldea-issuer/state as chaldea-issuer:chaldea-issuer 0700.
   As that UID, umask 077; openssl genpkey -algorithm ED25519 -out
   /var/lib/chaldea-issuer/keys/agent-a-2026-10.pem. Owner chaldea-issuer,
   mode 0600, single regular file. HostIssuer's loadHostSigningKey reads it.
   Private material stays on its issuer host, outside all sandbox mounts,
   env and FDs. This task/role generates no key or identity.
4. Extract the public JWK on each key's owning machine with trusted Node:

       node --input-type=module -e 'import {readFileSync} from "node:fs"; import {createPublicKey} from "node:crypto"; const {kty,crv,x}=createPublicKey(readFileSync(process.argv[1])).export({format:"jwk"}); console.log(JSON.stringify({kty,crv,x}));' <absolute-private-path>

   Transfer **only** public output to Igor. Add the issuer's public record to
   access-trust/issuer-grants.json: issuer chaldea:agent-a, unique kid,
   public_key, integer not_before/issue_until/verify_until and exact ceilings.
   Require not_before < issue_until <= verify_until, difference <=810s.
   Choose issuance lifetime deliberately; bundle freshness is separate.
   Akasha ceilings include audience akasha, profile/project/source and exact
   resource/actions from its reviewed registry. Never guess broad grants.
5. On omarchy-pc, create private publisher state directory 0700. Initialize once:

       chaldea access initialize-state --state-file <publisher-state-dir>/publisher.sqlite
       sudo install -d -o root -g root -m 0755 /run/chaldea-access-trust
       sudo /opt/chaldea/node/bin/node /opt/chaldea/app/src/access/maintenance.ts clock-health --output /run/chaldea-access-trust/clock-health.json
       chaldea access sign-bundle --state-file <publisher-state-dir>/publisher.sqlite --clock-health-file /run/chaldea-access-trust/clock-health.json --key-file <deployment-private-path> --kid deployment-2026-10 --grants-file <fleet-checkout>/access-trust/issuer-grants.json --sequence <increasing-N> --output <private-publisher-dir>/bundle.jws

   Commit/review/push only the signed output as access-trust/bundle.jws with
   reviewed public grants. Retain the same durable publisher state and use
   increasing sequences; serialize signing. If signing fails after committing state
   but before output, re-sign with a higher sequence instead of resetting state. Empty [] grants revoke all issuers;
   never accidentally publish the initial template.
   Igor owns renewal automation on omarchy-pc: establish and verify it before
   activation, recommended every 6h plus immediate changes. It refreshes clock
   evidence immediately before signing and alerts before expiry. Only Igor's
   publisher process may read the anchor. The root health command reads only chrony's
   protected socket; it does not read the anchor. Install the same pinned runtime on
   omarchy-pc for this command. Automate health through the reviewed root oneshot
   or a narrowly approved invocation, never a general sandbox sudo rule. A 6h cadence leaves 18–24h remaining
   outage tolerance; a full 24h is the maximum from publication.
6. Before enabling homelab's role, provision root:root files
   /etc/chaldea-access-trust/deploy-key (0600, unique read-only GitHub deploy key)
   and known_hosts (0644, independently verified GitHub host key).
   Never use unverified ssh-keyscan output or the operator's private key.
   Create /var/lib/chaldea-access-trust root:root 0700 and initialize once as root:

       /opt/chaldea/node/bin/node /opt/chaldea/app/src/access/maintenance.ts initialize-state --state-file /var/lib/chaldea-access-trust/updater.sqlite

   Initialization is exclusive. Convergence never creates/resets the DB.
   Preserve state through backup/reinstall; missing/corrupt state parks access.
7. Set chaldea_access_trust_enabled=true and independently pinned public anchors
   only in homelab's approved inventory. Check then apply only
   --limit homelab --tags chaldea_access_trust through local ansible-pull.
   Units: chaldea-clock-health.service/.timer (10s) and
   chaldea-access-trust.service/.timer (120s). Verify status/journal, first
   successful install sequence/expiry, ownership/modes and second-apply
   idempotence. No issuer key is touched.
8. Akasha config on homelab uses bundle_file and akasha_trust_bundle =
   /var/lib/chaldea-access-trust-public/bundle.jws; clock_health_file and
   akasha_clock_health = /run/chaldea-access-trust/clock-health.json.
   Directories root:root 0755, files root:root 0644. If mount isolation is used,
   bind the **directories** read-only so atomic replacements stay visible.
   Config anchors must match the independently pinned keys.
   Initialize Akasha's separate access_state once as its service UID with
   initialize-state, in a service-owned 0700 directory, DB 0600.
   Never share the root updater SQLite or restore older high-water state.
   Start Akasha only after current trust and health exist. Requests check
   clock/expiry immediately; Akasha reloads the public file every 120s.
   Apply equivalent private-state/clock requirements to the future agent-a
   issuer, inaccessible to sandbox UIDs.
9. Before akasha_interfaces_verified, run approved canaries: tamper, same/lower
   sequence, removal, overlap rotation, restart, stale health, offset >30s,
   clock rollback and publisher loss through signed expiry, plus Akasha's
   runtime/ACL/backup gates. This PR sets no activation flag or schedule.

## Rotation and recovery

Publish new public key/kid/material, confirm required updater sequence/expiry
receipts and Akasha reload, then activate new issuance. Stop old issuance,
publish shorter issue_until and verify_until <=cutoff+810, retain verification
for outstanding tokens, then remove. Removed identities/material cannot return;
deadlines cannot extend under an existing ID. Emergency removal overrides overlap.
A higher-sequence empty-keys bundle revokes all. Anchor rotation is explicit
operator-pinned deployment with overlap and verification, never self-authenticated.

The installer commits TrustStore high-water/key history before replacing public
bytes atomically. Interrupted replacement retries identical bytes. Failed
fetch/signature/clock checks preserve signed expiry. Missing state needs diagnosis,
never automatic reinitialization or old DB restore. Disk-full parks access.
The bare Git cache is transport data and may be deleted while timers are stopped;
never delete updater/verifier SQLite to clear a failure. Units serialize updates;
manual updates use systemctl start rather than a competing process.

## Checks

TMPDIR=<absolute disk scratch> bash tools/ci.sh establishes synthetic HOME and
fleet_home before tests. New pytest covers byte-only fetch arguments, preserved
public bytes on transport/verification failure, size/key permissions, disabled
inventory and rendered units. Chaldea tests exercise real signature/history/time
checks with disposable generated fixture keys. No real homes, system managers
or hosts are used. Live canaries remain a later approved rollout.
