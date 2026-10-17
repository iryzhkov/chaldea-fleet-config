# Chaldea access trust (package F, trust slice)

Source-only packaging. Fleet enrollment remains disabled. The first public issuer
and deployment anchor are pinned; no signed bundle, private keys or host changes
are included. Run-profile UID, T3,
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
operator-compared Ed25519 deployment anchor. Its public pin is committed in this
same repository; repo-write protection and the existing root ansible-pull channel
are therefore part of the trust base. The signature does not defend against an
attacker who can rewrite root fleet configuration. The bare cache never checks out
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

1. Freeze reviewed Chaldea/fleet commits and successful CI. Install the public
   host release through chaldea_host_artifact using the inventory version and
   SHA-256; see [host installation](host-artifact.md). The bundled maintenance
   entry point is /opt/chaldea-host/releases/VERSION/host/access-maintenance.mjs.
   It includes production dependencies; do not separately stage a source tree or
   run npm on the deployment host. Separately install pinned Node 26.10.0 at
   /opt/chaldea/node/bin/node on homelab and omarchy-pc (later agent-a).
   The node, bundled runtime and ancestors must be real, root-owned paths without
   group/other write; updater and clock ExecStartPre check this on every start.
   ProtectHome requires runtime outside /home. Use the rendered role values:

       CHALDEA_HOST_VERSION=<inventory-chaldea_host_version>
       CHALDEA_ACCESS_NODE=/opt/chaldea/node/bin/node
       CHALDEA_ACCESS_RUNTIME=/opt/chaldea-host/releases/$CHALDEA_HOST_VERSION/host/access-maintenance.mjs

   CHALDEA_ACCESS_NODE must equal the reviewed chaldea_access_trust_node setting.
   Bundle, clock-health, updater and verifier state paths below come from the
   single inventory chaldea_access_paths mapping; override examples with its
   rendered values if an approved configuration changes them.
   Provision git, openssh-client and python3 on these approved hosts. The clock
   adapter supports systemd-timesyncd and chrony. Homelab, omarchy-pc and agent-a
   keep timesyncd; there is no time-service migration. On active timesyncd the
   adapter requires NTPSynchronized plus valid, recent NTPMessage timestamps via
   the system D-Bus. With timesyncd inactive, chrony uses the root-protected
   /run/chrony/chronyd.sock socket, with no UDP fallback or local/orphan mode.
   Unknown/unsynchronised status fails closed; the conservative 30s offset bound
   and fresh 30s evidence apply to both. Use independent external time sources.
   This role does not install or change time services.
2. **First-time enrollment of a new kid only. Skip this step for the already
   pinned deployment-2026-10 key; use its existing protected path.**
   Igor, as igor on **omarchy-pc only**, creates
   /home/igor/.local/share/chaldea-access-publisher/keys (owner igor, 0700).
   For a genuinely new key, use a subshell with umask 077 and set -C
   (noclobber), then openssl genpkey -algorithm ED25519 > <new-key-path>.
   Shell exclusive creation refuses an existing path; do not use -out on a live key. The PKCS8 file is igor-owned 0600,
   single-link. Protect ancestors. Igor holds its protected offline backup;
   omarchy-pc holds the sole live deployment key. Never copy it to a run host,
   sandbox, repository, env or transcript. omarchy-pc also hosts compute jobs:
   provision the live key only after canaries prove those sandboxes and restricted
   UIDs cannot read Igor's publisher directory or use sudo. Interactive full-access
   operator agents running as igor/root remain trusted and can read it; 0700/0600
   does not isolate it from that operator identity. If that trust is unacceptable,
   use a separately reviewed publisher UID or protected signer before creating it.
   Independently compare its public
   fingerprint/JWK before pinning chaldea_access_trust_anchors in approved
   inventory and Akasha config.
3. **First-time issuer enrollment only. Skip key creation for the already
   pinned agent-a-2026-10 key.** For each new approved issuer, the operator separately provisions
   locked service identity chaldea-issuer, distinct from the run UID, without
   login, sudo or operator groups. Create /var/lib/chaldea-issuer/keys and
   /var/lib/chaldea-issuer/state as chaldea-issuer:chaldea-issuer 0700.
   As that UID, use a subshell with umask 077 and set -C, then
   openssl genpkey -algorithm ED25519 > <new-issuer-key-path>.
   Noclobber refuses existing files; never target the live issuer key. Owner chaldea-issuer,
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

       "$CHALDEA_ACCESS_NODE" "$CHALDEA_ACCESS_RUNTIME" initialize-state --state-file <publisher-state-dir>/publisher.sqlite
       sudo install -d -o root -g root -m 0755 /run/chaldea-access-trust
       sudo "$CHALDEA_ACCESS_NODE" "$CHALDEA_ACCESS_RUNTIME" clock-health --output /run/chaldea-access-trust/clock-health.json
       "$CHALDEA_ACCESS_NODE" "$CHALDEA_ACCESS_RUNTIME" sign-bundle --state-file <publisher-state-dir>/publisher.sqlite --clock-health-file /run/chaldea-access-trust/clock-health.json --key-file <deployment-private-path> --kid deployment-2026-10 --grants-file <fleet-checkout>/access-trust/issuer-grants.json --sequence <increasing-N> --output <private-publisher-dir>/bundle.jws

   Commit/review/push only the signed output as access-trust/bundle.jws with
   reviewed public grants. Retain the same durable publisher state and use
   increasing sequences; serialize signing. If signing fails after committing state
   but before output, re-sign with a higher sequence instead of resetting state. Empty [] grants revoke all issuers;
   never accidentally publish the initial template.
   Igor owns renewal automation on omarchy-pc: establish and verify it before
   activation, recommended every 6h plus immediate changes. It refreshes clock
   evidence immediately before signing and alerts before expiry. Only Igor's
   publisher process may read the anchor. The root health command reads only time
   service status; it does not read the anchor. Install the same pinned runtime on
   omarchy-pc for this command. Automate health through the reviewed root oneshot
   or a narrowly approved invocation, never a general sandbox sudo rule. A 6h cadence leaves 18–24h remaining
   outage tolerance; a full 24h is the maximum from publication.
6. Before enabling homelab's role, provision root:root files
   /etc/chaldea-access-trust/deploy-key (0600, unique read-only GitHub deploy key)
   and known_hosts (0644, independently verified GitHub host key).
   Never use unverified ssh-keyscan output or the operator's private key.
   Create /var/lib/chaldea-access-trust root:root 0700 and initialize once as root:

       sudo "$CHALDEA_ACCESS_NODE" "$CHALDEA_ACCESS_RUNTIME" initialize-state --state-file /var/lib/chaldea-access-trust/updater.sqlite

   Initialization is exclusive. Convergence never creates/resets the DB.
   Preserve state through backup/reinstall; missing/corrupt state parks access.
7. Homelab is managed by homelab-infra, with playbooks run from omarchy-pc.
   Keep fleet inventory chaldea_access_trust_enabled=false. Use homelab-infra's
   targeted playbook and the exact ordered commands in its
   [Akasha rollout runbook](https://github.com/iryzhkov/homelab-infra/blob/main/docs/akasha-v1-deployment.md).
   It ports these roles/templates and imports the single path convention.
   Bootstrap key/known_hosts/state ownership and modes are checked before timers
   start; state must already be initialized. The fixed runtime directory is
   /run/chaldea-access-trust. chronyc needs /run/chrony writable for its private
   reply socket, so only the clock unit allows that optional directory through ProtectSystem.
   The -/run/chrony entry permits a timesyncd host where that directory is absent.
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
   Initialize Akasha's separate access_state once as its service UID with the
   same bundled initialize-state command and chaldea_access_paths.verifier_state
   (/var/lib/akasha/access-state.db). Its parent is service-owned 0700 and the DB
   is 0600; the path is inside the unit's ReadWritePaths=/var/lib/akasha.
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

## First public enrollment (2026-10-17)

The deployment anchor is kid deployment-2026-10, SPKI SHA-256
222450438cdcae5bda6c498f5e39baee5e2479923389c28e518ccf9138aee296.
The agent-a-2026-10 issuer ceilings match homelab-infra's rendered source registry:
daily-health / homelab / chaldea.daily-health.agent-a (report),
fleet-timers / chaldea / agent-a.fleet (job_finished), and
toolfeedback / chaldea / agent-a.toolfeedback (tool_call). All are audience akasha,
append only, with exact source resources. No read or other service grants.
The issuance window is deliberately 30 days: 2026-10-17T00:00:00Z through
2026-11-16T00:00:00Z (exclusive); verify_until is 2026-11-16T00:13:30Z,
exactly 810 seconds later. Renew/rotate before the cutoff; do not extend an
existing kid's deadlines. Bundle freshness remains a separate 24h lease.

The current inventory host-v0.1.1 pin is preserved. It predates timesyncd and the
bundled Akasha service, so it is not a deployment-ready artifact for this rollout.
After Chaldea merges, the orchestrator tags a release from main, verifies CI and
updates version/SHA-256 identically in both inventories before signing/deploying.
No release is cut by this implementation task. Existing deployment/issuer private
keys are operator-provisioned; do not regenerate them by following generic key
creation examples above. The homelab-infra runbook is the ordered rollout procedure.
