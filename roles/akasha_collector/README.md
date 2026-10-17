The role installs one host collector timer, disabled by default. The shared pinned
host artifact supplies `akasha-collector.mjs` and one timer reporter.
`akasha_collector_enabled` selects `queue` delivery in
`~/.config/chaldea/timer-reporting.json` and enables the collector; the default is
`feed`. A missing or failing helper in queue mode leaves events queued.
Deployment must supply the pinned Node executable, HTTPS ingress, and an absolute
token-helper executable. The artifact's bundled collector needs Node with SQLite;
it does not need a Chaldea source checkout or installed npm dependencies.
The helper receives --audience akasha --action append --source SOURCE --host HOST
--kind KIND, writes only a compact JWT to stdout, and must grant a service
principal with stable issuer/profile/project/source/host across fresh leases.
It is called for every delivery attempt; neither producers nor collector read
a shared feed key. Missing helpers leave events queued.

Quota uses chaldea-quota; tool calls use HOST.toolfeedback and timer outcomes
HOST.fleet (job_finished). Register those source/kind bindings at the gateway.
Timer keys are JOB/INVOCATION_ID, including OnFailure. Immutable delivered inputs remain for 90 days, so a wrapper crash before its status claim reuses the original payload. Timers only enqueue;
quiet successful invocations remain quiet. The spool holds at most 8 MiB and
1,024 files, accounting for allocated filesystem blocks and directory space, with a persistent dropped counter at timer-spool-count.json.
A queue-full outcome remains visible locally and does not change the job exit.

The collector's DELETE-journal database is limited to 16 MiB plus a rollback journal of approximately the same size
(with journal headers covered by the host budget margin), quota state to 8 MiB plus its atomic temporary file, and
timer input to 8 MiB. Together these new event states stay below 64 MiB.
Raw toolfeedback remains best-effort instrumentation input, not a byte-capped
queue; it is pruned at 90 days and expired unshipped complete lines are counted.
Collector offsets advance only on a visible central receipt, independently of
the old Loki shipper. Leave that shipper running until parity and retirement
approval; this role does not disable it. No host was deployed by this PR.
