# Hosted Mission Control qualified packet

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
