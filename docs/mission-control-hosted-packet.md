# Hosted Mission Control qualified packet

## Rich resources and thread details, C58

Client-v0.4.7 and host-v0.2.7 are immutable releases from merged
445e730124f3e99c78cba663300e72635f2740ca. ROOT downloaded all four assets
and matched the agent-a double-build qualification in
jocasta:3d3fb074ce60e538ac359f0cbdb7ccf8@1.
Client archive SHA 9c5d1f1d087010d32c5309c3099098b85e5de7015d9a524e2af03f01689861b3,
manifest SHA b32de16b9b39c192dda21568735222bd47d0e87ca711a4b830ac44de615bce7b.
Host archive SHA fabf83d5814a8c997f57691dea4b711b245ffd37b29783b1e0fd1b0ec122e218,
manifest SHA f8c31218cc1b5a569aa690115feeae8c1cc3ed02775878a358eb582469def2b8.

Before this collector-selection change merges, stage027 on A/PC/B/L through
the unchanged canonical artifact role, preserving every actual old release
and cache. Fresh preflight: H[022,023,024,026], PC[021,022,024,026],
A[022,024,026], B[021,022,026], L[011,022,026]. These are staging027
preserve sets. The inventory sets instead protect every NONselected release
during ordinary shared022 calls, including027. MAX4 limits the explicit list,
not the total installed releases. Never replace a staging set with the
shared022 set, raise the bound, or prune an old release.

Qualify compatible H027 and N047 readers plus ALL four ordinary027 collectors
BEFORE activating rich047 captures. Keep the existing registry28, ordered
A/PC/B/canonical-L sources, every grant and signed ceiling, shared022,
helper040, ordinary clients and T3 unchanged. No signer or helper replay.
Use the new exact H host-version/hash qualification variables, installed
SYSTEM verification before activation, protected snapshots and SECOND changed=0.
Cold CHECK is not installed-unit verification. No --step or prompt driver.
New fields and provider permissions require actual live proof; old046 remains
valid during the consumer-first upgrade. No latency SLA or all-page claim.

## B/L source activation, 2026-10-19

The B/L collector selections require host-v0.2.6 staged BEFORE this change merges
or a normal pull consumes it. Archive SHA
504326b4d617b8d4f5972f9fab07f6c7c52f6194c1fc149eb9610d5dcba1d74d,
manifest SHA 3b802e13dd92e1d86719330423b1c04cd97d8ae92c0c4f9a51f6d68ce045350b,
native manifest has 11 members. Shared022, helper040 and ordinary clients stay pinned.
Strict known-host public metadata probes found B UID1000 with host021/022 and
L canonical omarchy-macbook-air-igor UID1001 with host011/022. Inventory preserves
those exact releases plus026. Revalidate actual preservation before operator work.

The same public-only native composition selects pc_reader=true, pc_quota=true,
laptop_quota=false, pc_quota_reader=false. Mission Control publisher UIDs are
A1000/PC1000/B1000/L1001 and reader940. Ordered reader sources are
agent-a--mission-control, omarchy-pc--mission-control, agent-b--mission-control,
omarchy-macbook-air-igor--mission-control. Only B/L append ceilings and their
agent_status helper grants are added; preserve every existing key, window and grant.

ROOT owns final clean-head reviews, native CI and operator release. Stage B/L026
before merge. Later canonical H runs require explicit
mission_control_laptop_qualified=true,
mission_control_laptop_host_version=host-v0.2.6 and
mission_control_laptop_host_sha256=504326b4d617b8d4f5972f9fab07f6c7c52f6194c1fc149eb9610d5dcba1d74d,
independent of laptop permission. Preserve H registry26, add only B/L to reach28,
then the four-source N reader. Qualify actual B/L runtime, UID/token permission,
private snapshot and installed SYSTEM gates before capture; complete helper policy
from the SAME native render and enable ordinary collectors last. Require inspected
CHECK, REAL, SECOND changed=0 and protected before/after state at each selected host.
Source/native output is not installation, a signing run or live qualification.

## Historical canary packet

The completed canary and its limits are recorded in
jocasta:7809f6329c87f8a3c5390221ee4d0d2e@2. Source qualification is
jocasta:623f53e1c960b0383b2a44b3afcbb981@1, actual package job
f15bba62-b8c3-4529-8df3-f91952b3f82d on Node26.10.

The explicit playbooks/vars/mission-control-deployment.yml selects client-v0.4.4
archive SHA da4b457e7885ffea3dde51c7e93160e90f2e81566d2e33fb9211fb07ca146ca4.
Release416721739/archive654521129/manifest654521136/run39167627844;
manifest SHA2a3f4c8d47a2fe888def2de51bdb0fe78c632b59f5b8e7a005eb5fd813ce0fc4.
Published assets are immutable and must not be rebuilt or replaced.

Homelab server and agent-a collector use the already qualified host-v0.2.4 archive
SHA531710066a7f67ac68f82ad1234d8f9a32e3311c839a894f86125c7d4f170592.
Release416722339/archive654523759/manifest654523754/run39167630357;
manifest SHA0fd697257963498e1f946e4fb5274a0c141cf5287120b6d6617721aa0e788a72.
Infra owns the canonical Homelab pin and role-local022/023 preservation.

Use the qualified packet only as explicit extra-vars. Its enabled flags and
mission_control_activate remain false until the exact reviewed invocation selects
them. Inventory supplies the collector snapshot input without an empty packet override.
For agent-a use playbooks/mission-control.yml --limit agent-a. For Normandy use
infra's play with the exact clean reviewed fleet checkout and ANSIBLE_LIBRARY.
See mission-control-hosted.md for stage, verify and activate behavior.

Existing six issuer public keys and every old ceiling/grant remain intact.
The already reviewed SAME native render supplied the publisher UID1000 append-only
agent-a.mission-control/agent_status/projectchaldea grant and the dedicated reader
UID940 read-only mission-control-reader grant, restricted to agent-a--mission-control.
The reader role's one-row grants assertion is not a complete helper grant list.
Never replace old grants with it. No new signing, publication, mint or enrollment is
required by this cleanup. Existing canonical registry additions are enrollment-gated;
the separate infra proposal stays empty and unused.

Before any separately authorized live convergence, inspect CHECK/diff, perform REAL
and SECOND changed=0, and preserve protected state/PIDs/timers. Revalidate dedicated
identity ownership, issuer-only sudo/DAC and namespace constraints, web read/no-write,
exact target SYSTEM units, edge-only7393/BPF, Host/Origin and SSE freshness.
Source fixtures are isolated evidence, not actual target qualification or a live
broker/thread-transition/outage proof. Root owns combined reviews and deployment.
