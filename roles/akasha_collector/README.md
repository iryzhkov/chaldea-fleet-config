The role installs one host collector timer, disabled by default. Deployment must
supply the pinned Node executable, the Chaldea source tree containing
src/events/collector.ts, HTTPS ingress, and an absolute token-helper executable.
The helper receives --audience akasha --action append --source SOURCE --host HOST
--kind KIND, writes only a compact JWT to stdout, and must grant a service
principal with stable issuer/profile/project/source/host across fresh leases.
It is called for every delivery attempt; neither producers nor collector read
a shared feed key. Missing helpers leave events queued.

Quota uses chaldea-quota; tool calls use HOST.toolfeedback and timer outcomes
HOST.fleet (job_finished). Register those source/kind bindings at the gateway.
Timer keys are JOB/INVOCATION_ID, including OnFailure. Timers only enqueue;
quiet successful invocations remain quiet. The spool holds at most 8 MiB and
10,000 files, with a persistent dropped counter at timer-spool-count.json.
A queue-full outcome remains visible locally and does not change the job exit.

The collector's DELETE-journal database is limited to 16 MiB plus at most 16 MiB
of rollback journal, quota state to 8 MiB plus its atomic temporary file, and
timer input to 8 MiB. Together these new event states stay below 64 MiB.
Raw toolfeedback remains best-effort instrumentation input, not a byte-capped
queue; it is pruned at 90 days and expired unshipped complete lines are counted.
Collector offsets advance only on a visible central receipt, independently of
the old Loki shipper. Leave that shipper running until parity and retirement
approval; this role does not disable it. No host was deployed by this PR.
