# Hosted Mission Control source

All new roles and routing default off. No active inventory or issuer data is changed.
The agent-a capture uses playbooks/mission-control.yml with a literal --limit agent-a.
Normandy is composed only by homelab-infra's one-host Mission Control play.
Neither play installs T3 or changes quota, helper release, user client or Akasha units.

Select a newly published hosted client version and archive SHA only after its source,
archive/manifest, imports and assets have passed the root-owned combined review and
Node26.10 qualification. Defaults deliberately name no release. The existing helper
client-v0.4.0 and validator Node26.12 remain independent.

The runtime role calls library/chaldea_client_release.py unchanged into
/opt/chaldea-mission-control/releases/VERSION. It checks every manifest member,
archive hash and existing immutable tree. Units name the exact version.
Do not point this root at the helper or user-client tree.

## Unapplied permission packet

playbooks/vars/mission-control-proposal.yml records missing UID inputs, not grants.
The public generator accepts an optional mission_control object with publisher_uid,
reader_uid and read_sources. Explicit publisher UID1000 selects only agent-a append
of agent_status, source agent-a.mission-control, profile mission-control-publisher,
project chaldea and source_id agent-a--mission-control. A dedicated reader UID with
read_sources [agent-a--mission-control] selects service read only, source/profile
mission-control-reader on omarchy-normandy, kind agent_status, project chaldea.
No global_read, quota_fleet_read or raw feed access is emitted.
An all-null/empty packet is equivalent to omission.

Run tools/akasha-enrollment-inputs.mjs with a qualified hosted client as its first
argument and existing public policy/key inputs on stdin. That client's strict
Authorization decoder must accept mission_control_read_sources. The existing
enrollment play deliberately still validates its original path with0.4.0; do not
feed a new packet through that old validator or upgrade it implicitly. Root must
review the generated ceilings, helper grants and registry together before a separate
exact one-host helper invocation. Enabling a role never generates a grant.
The reader role requires the exact reviewed mission_control_reader_grants as input.

## Ownership and activation gates

Reader UID stays null until selected and qualified. It must be a new locked account,
never igor or another enrolled service. Qualify its actual sudo -l confinement to only
/usr/local/libexec/chaldea-token-helper-issuer --audience akasha --action read
--source mission-control-reader --host omarchy-normandy --kind agent_status.
The web account receives no helper grant, token or sudo. Capture and web keep NNPyes.
Only this dedicated reader uses NNPno for the existing issuer sudo hop.

Reader state is0700. Reader configuration is root:mission-control-reader0640 inside
a0750 directory. The cache is reader:mission-control-cache2750. The writer creates
a same-directory temporary file, sets0640, then renames it, preserving the SGID group.
The web account has read/traverse access through that group and cannot write cache.

Capture reads only metadata of the existing igor-owned0600 token before starting.
Its sanitized own latest file is the only capture writable path. Source token
semantics remain unqualified. The collector snapshot input is absent by default;
selecting it requires the matching newly released host collector artifact too.
No timer frequency changes are included.

Before live activation root must qualify dedicated UID availability, exact helper
confinement and signed ceilings, source/registry equality, artifact custody and
actual source latency. No credentials are transferred. Existing grants and PC quota,
sharing, collector limits and routing configuration remain unchanged.

Rollback disables the LAN router and stops only the new Mission Control services,
then restores a qualified previous exact release/config. Keep the previous release
and bounded cache for14days. No trust rollback, T3 restart or unrelated grant removal.
