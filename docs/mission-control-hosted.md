# Hosted Mission Control deployment

The LAN canary is deployed at https://chaldeas.ryzhkov.dev. It currently transports
one agent-a sanitized status source with zero rows. PC threads, jobs, quota and
roadmap progress are not connected. Token semantics and a real non-PC thread
transition/outage remain unqualified. Completed deployment evidence and limits:
jocasta:7809f6329c87f8a3c5390221ee4d0d2e@2.

All service enabled flags and mission_control_activate default false. The explicit
agent-a play requires literal --limit agent-a and local connection. Normandy belongs
to homelab-infra's literal one-host composition, never fleet site ownership.

With selected enabled flags true, main tasks stage accounts, directories, config
and exact units. Stage-only real runs refuse selected active or enabled units before
staging writes. Use one complete invocation with mission_control_activate=true for
warm updates. Includes retain config/unit changed results, so changed services restart
and an unchanged second real run changes nothing. Do not stage in one invocation and
activate in another. There are no persistent activation markers.

The capture activation task runs target SYSTEM-mode systemd-analyze verify --man=no
against its exact installed service before any manager action. Infra verifies the exact
reader, web, ingress socket and ingress service together before invoking reader and
web/ingress activation tasks. Verification failure prevents activation. CHECK validates
the contract and shows warm config/unit template diffs when required identities and
parents exist. Cold CHECK explicitly defers unmaterializable staging. SYSTEM verification
is deferred in CHECK; predicted files and accounts are not qualified. False flags do not stop or roll back active services.

The unchanged canonical installer validates the selected immutable release under
/opt/chaldea-mission-control/releases/VERSION. Existing helper client-v0.4.0,
validator Node26.12, user clients, T3 and quota services remain independent.
Reader UID940 has only its exact approved issuer sudo command. Its NNP=no permits
that hop; issuer directory0700/SQLite0600 still deny direct reader access. Web and
capture retain NNP=yes. Reader state0700/config0640 and cache2750/atomic file0640
remain required. Web has cache read access without write, helper, sudo or token access.

Capture only stats the existing private token and writes its own sanitized snapshot.
The deployment packet no longer overrides the collector snapshot input. Existing
agent-a inventory supplies /home/igor/.local/state/chaldea/mission-control/latest.json.
Collector host024 is role-scoped; global shared trust remains022 and cadence stays
30s plus5s jitter. No automatic grant, publisher, signing or credential operation
belongs to staging or activation.

## Optional Events/Ops reads

`mission_control_reader_operations_enabled` defaults false. Off, reader.json has
no `operationsEnabled` key, so older reader parsers see the same bytes. On, the
reader role writes `operationsEnabled: true` and refuses to stage unless the
runtime client is at least 0.4.9, all four status sources are selected, and
`mission_control_reader_grants` is exactly the status row followed by the same
UID940/source/host/profile/project read rows for `job_finished` and `report`.
This is a compatibility guard; it does not mean a 0.4.9 release exists.

The native enrollment adapter takes the matching optional
`mission_control.operations_read` boolean. False or absent renders exactly the
current output. True requires the selected reader with all four status sources and
adds only those two Normandy helper rows plus `mission_control_operations_read:
true` and kinds `[agent_status, job_finished, report]` on the existing reader
registration. Issuers, keys, ceilings and `access-trust/issuer-grants.json` are
unchanged: ceilings carry resource and action, not kind.

The adapter's stdout remains the additive registry subset. With operations on it
also validates that subset together with the three infra base registrations
(agent-a daily-health, fleet and toolfeedback), because the reader binds two of
them. That proves the full composition decodes; homelab-infra still applies and
checks the full registry, and the Akasha server enforces it at startup.

Signed tokens authorize resource and action only; the kind is not cryptographically
bound. The local helper matches the kind exactly, and the server restricts the
reader through its registry flag and kinds, the one fixed
`/api/v1/events?mission_control_operations=job_finished|report&window=48h&limit=16`
selector and full source-tuple binding.

## Rollback

Rollback explicitly withdraws the owned route and stops/disables owned MC units,
then restores guarded prior config/releases. Preserve keys, antirollback state,
shared trust022 and server rollback023. Never restore old access databases.
