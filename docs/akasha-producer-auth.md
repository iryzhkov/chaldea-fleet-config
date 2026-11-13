# Akasha producer Authentik switch, P3.3 step 2

Source-only. All six host flags default false. Do not enable before the root
releases client-v0.4.27 and host-v0.2.21 from the merged Chaldea change and records
their independent archive digests. Latest tags at inventory were client-v0.4.26
and host-v0.2.20. Never invent a release digest.

## Read-only inventory, 2026-11-12

All rows use /usr/local/bin/chaldea-token-helper, which sudo runs as
chaldea-issuer through /usr/local/libexec/chaldea-token-helper-issuer.
That wrapper runs the protected client under /opt/chaldea-token-helper.
Root-owned /etc/chaldea/token-helper.json selects the issuer key below
/var/lib/chaldea-issuer/keys and exact producer UID, source, host and kind.
Live public config and timer/unit inspection confirmed this on every host.

| Host | Producers and readers | Producer UID | Configuration owner |
| --- | --- | --- | --- |
| laptop, registry omarchy-macbook-air-igor | collector; feed; toolfeedback spool/ship; fleet job_finished; mission-control agent_status; fleet-reader | 1001 | fleet-config |
| omarchy-pc | collector; feed; toolfeedback spool/ship; fleet job_finished; mission-control agent_status; quota events; fleet-reader and route score reader | 1000 | fleet-config |
| agent-a | collector; feed; toolfeedback spool/ship; fleet job_finished; mission-control agent_status; fleet-reader | 1000 | fleet-config |
| agent-b | collector; feed; toolfeedback spool/ship; fleet job_finished; mission-control agent_status; fleet-reader | 1000 | fleet-config |
| homelab | collector; feed sources feed/backup/drift-check/offsite; toolfeedback spool; route_score_snapshot publisher | 1000; route publisher 0 | homelab-infra for producer enrollment/route; fleet-config for collector |
| normandy, registry omarchy-normandy | collector; feed sources backup/drift-check; toolfeedback spool; retired reader grants removed by infra | 1000 | homelab-infra for enrollment; fleet-config for collector |

Round 1 live audit found only Normandy UID 940 outside root/the producer UID:
mission-control-reader reads for agent_status, job_finished and report. No Mission
Control units remain on any host. Infra removes these three retired grants before
regenerating sudoers; no affected live consumer remains. The other five hosts have
no refused caller grants. Inspect the public config again before each cutover;
retain any newly discovered live narrow caller on PKI and block that host's enablement. No job_finished grant
exists for homelab or Normandy; their collector timer events are deliberately off.
Do not add grants during migration. Their feed append canary must use backup,
not an ungranted generic feed source on Normandy. Read homelab/Normandy receipts
from the existing interactive fleet-reader rather than granting a new reader.

Chaldea owns helper, collector, job_finished, quota/status publishers and route
transport. homelab-cli owns feed, toolfeedback and their spool formats. These
clients lacked X-Akasha-Source; both source PRs add it. Existing collector,
route publisher and route-reader bundles must be upgraded before mode selection.
Feed/toolfeedback need the homelab-cli PR installed through their existing source pin.
No Akasha server change is included.

Authentication and credential custody: see Chaldea docs/token-helper.md.

## Per-host enablement

Retain a private rollback copy of public helper config, wrapper, launcher and
sudoers, plus exact existing release pins. Preserve all PKI keys, state and trust.
Use a fresh reviewed checkout of both infra repos and both inventories for servers.
Use the normal SSH user without global become, since gathered home/UID must identify
the credential owner. TMPDIR and ANSIBLE_LOCAL_TEMP stay below task scratch.

Set the qualified client-v0.4.27 archive version/digest through protected operator
vars chaldea_token_helper_client_version and chaldea_token_helper_client_sha256.
Install the header-capable host collector, route publisher/reader runtimes and
homelab-cli source pin using their existing qualified workflows first. Do not run
shared-root GC as part of this helper-only playbook.

Set chaldea_token_helper_authentik_enabled: true persistently in that host's
fleet inventory/host_vars/HOST/akasha-auth.yml, or infra inventory/host_vars/HOST.yml
for homelab/normandy. Commit the selected host only; do not pass a global mode -e.
For laptop/omarchy-pc/agent-a/agent-b run fleet-config
playbooks/akasha-producer-auth.yml with --limit HOST and protected release pin vars.
First --check --diff, review,
then apply and repeat for zero changes. This explicit playbook reuses the current
public enrollment and does not run trust updater installation. ANSIBLE_ROLES_PATH
must include the reviewed fleet-config roles and ANSIBLE_LIBRARY its library.
Also load inventory/group_vars/all/main.yml for pinned Node checksum inventory.

For homelab/normandy run homelab-infra playbooks/akasha-producer-auth.yml with
the same arguments, both inventories, and chaldea_fleet_config_checkout set to
the reviewed absolute fleet-config checkout. Infra imports the shared implementation.
On homelab it also binds only the credential directory read-only through the
route service's ProtectHome namespace. No automatic service start occurs.
Always limit one host; preserve aliases laptop/normandy for Authentik usernames.
Normal site.yml reads that same host variable. Canonical akasha-enrollment.yml
requires the normal alias hostvars from the fleet inventory plus infra inventory
for servers, and uses their persistent mode; a missing selection refuses rather
than reverting to PKI. Supply the same qualified helper release pins on all paths.

1. Feed: post a uniquely titled canary with --source feed on interactive hosts,
   --source backup on servers. Read its exact returned ID via feed show on a
   qualified interactive fleet-reader; check host/source/provenance and uniqueness.
2. Toolfeedback: run toolfeedback ship, then the user akasha-collector.service.
   Query the migrated host's tool_call source from a qualified interactive reader.
   Require a fresh persisted event and source cursor progress, not just exit zero.
3. Jobs on the four agent hosts: run a harmless chaldea exec -- true from a scratch
   repository, run the collector, then verify its unique job_finished ID, host,
   source and visible receipt. Do not create server job grants for this check.
4. Route on homelab: verify issuance inside chaldea-route-scores.service's namespace
   with ProtectHome=tmpfs and the read-only credential bind, then start the service;
   use its existing cached daily snapshot, avoiding a forced paid AA refresh.
   Verify a route_score_snapshot event with verified homelab provenance, then
   refresh/read it through the omarchy-pc route reader and verify exact delivery.
5. Check quota/status events where granted. Test selected-mode issuance failure in a synthetic fixture, never by
   damaging the production credential. Source tests cover redaction and fail-closed.
6. Record exact revisions, installed pins, accepted event IDs and check/apply/repeat
   outcomes per host before moving to the next. Server append-only scope stays as is.

## Rollback

Set the same host's persistent chaldea_token_helper_authentik_enabled back to false
in its owning inventory, commit, then check, apply and repeat the helper playbook.
It removes authentik from config and restores chaldea-issuer launcher/sudo target.
Infra also removes the homelab route namespace drop-in and reloads systemd.
Header-capable client/collector releases remain PKI-compatible; no downgrade is
needed. Verify one append/read and the affected producer receipts again.
Keep server dual acceptance enabled and retain all data, credentials and PKI state.
