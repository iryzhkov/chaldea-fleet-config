---
name: chaldea
description: >-
  Use Chaldea for builds, tests and heavy runs on fleet job hosts, explicitly
  requested non-executor time/thread waits, and questions in Igor's decision inbox.
  Reviews and worker briefs belong to review-delegation.
---

# Chaldea in T3 sessions

Chaldea adds fleet compute, durable waits and a decision inbox to T3. Keep using
T3's native `delegate_task` completion and `watch_pull_request` for actual child
and PR dependencies. PR checks/comments/conflicts can wake; merge ends the watch
silently. Handle your own authorized merge after CI and continue, or retain an
owner/recovery action for an external merge. Use `review-delegation` for reviews.
Registration does not finish an executor assignment; continue ready work before
yielding. Executor skills own temporary pin/checkpoint cleanup. A native pin
excludes automatic settlement; it is neither a keepalive nor permission.
Use Stop/cancel to cancel an assignment and its children. Manual Settle only
organizes thread state; native child completion may reopen it. Stop/user
cancellation still wins; do not promise native preservation of manual Settle.

On official T3 0.1.0, do not substitute external Chaldea time/thread wakes for
executor dependencies requiring Stop preservation. Client 0.4.11 can deliver a
stale external wake after offline Stop/resume. New guarded clients require server
capability absent from stock T3. Public replay cannot observe every idle Stop;
ordinary `message.dispatch` has no admission-version guard. Client preflight,
pinning and scheduler `runNow` do not establish atomic Stop safety. Preserve
historical guarded payloads fail-closed; never strip their guard or replay them
on stock T3. If a required native wake is unavailable, retain the exact gap, owner
and next authorized recovery in the existing checkpoint. No fork, new client
release, wrapper, store, daemon, fake recurring schedule or dummy child is needed
for the native executor path.

Restart T3 with `chaldea t3 restart`, never with `systemctl` directly.

`chaldea quota status` (or `--json`) reads the observer’s cached included-usage windows, aggregate Codex credits, advisory manual-reset inventory and each provider's capacity class, with per-metric freshness; it never spends credits or redeems resets.

## Route before delegating

Call FATE through `chaldea_route` or `chaldea route --role ROLE` before each T3
`delegate_task`. Use `builder` for implementation and main diff reviews,
`critical-review` for consequential design or disputed findings, `bulk-read` for
readers and `general` for other work. Pass the selected `providerInstanceId`,
`model` and `options` exactly as the delegate target, including effort. Chaldea
recommends; T3 launches the child. Honor explicit user/model overrides.

For the main other-provider review pass the writer's driver as `authorProvider`,
`claudeAgent` or `codex`, or CLI `--author-provider`. Route the independent peer
under `review-delegation`'s pair rule. A main review
normally uses `chaldea route --role builder --author-provider codex` for a
Codex author. Consequential design uses `critical-review`. A Codex-only builder
pin can legitimately refuse that main review. Use the approved other-provider
fallback below and in `review-delegation`; do not retry the pin indefinitely
or silently waive provider separation. Reject a same-provider target unless
that quota exception qualifies. Compare underlying provider drivers in the live
catalog before launching; a recommendation violating separation is unusable
and requires the documented other-provider fallback.

### CLI and outage fallback

A long-lived MCP can retain an older schema after a client upgrade. If it
rejects newer configuration keys, run the installed CLI with the same role
and author-provider constraint. Pass its exact target to T3. This is supported
without restarting T3; do not restart or alter configuration to recover routing.

If both routing paths fail or cannot recommend a target, record the reason
and resolve available provider/model IDs and effort options from
`orchestrator_capabilities`. This documented outage fallback uses Codex
Sol 6.1 high or Opus 5.5 medium for builders, Luna 6 medium for bulk reading and Sol 6.1 medium
for general work, conserving Claude. For a required main review, use the
approved Opus 5.5 medium / Sol 6.1 high pair on the other provider: Codex-authored
work uses Claude Opus, Claude-authored work uses Codex Sol. Consequential design
or disputed findings use Opus 5.5 high / Astra medium on the required other provider.
These are adopted outage anchors and explicit user overrides, not deployed router
changes; current critical-review routing still selects Fable until separate code changes.
Fable remains an optional explicit alternative.
If the fallback is unavailable, report why and apply `review-delegation`'s
quota or single-review rule for reviews; defer other dependent work.
Explicit user overrides still apply. Do not substitute an unavailable target
or represent fallback selection as a FATE recommendation.

Prefer two independent fresh-context reviews, Sol 6.1 high and Opus 5.5 medium,
using both providers whenever quota allows. `review-delegation`'s "Quota exception"
allows two different models on the same provider when quota is tight, with fresh
quota evidence and honest labeling. One independent review is acceptable when
quota or availability prevents the pair. Critical anchors are Opus 5.5 high and
Astra medium. Astra or an explicitly selected Fable can provide a stronger
available-provider peer; neither is a mandatory normal reviewer.
Unknown quota, missing routing recommendations or a collector HTTP 429 alone grant no waiver. Maximum effort is high; only Luna/Haiku may use xhigh.
These are ceilings, not defaults. Choose only available live-catalog models/options;
Haiku needs an available catalog target. Never use max, ultra, ultrathink or ultracode. Sonnet is excluded;
Haiku is allowed when selected. Avoid optional Claude fan-outs.

### Supported policy and deployment state

Role-target clients support live-catalog candidates, pins, bans, AA quality
floors/objectives and Slopalytics probation with quota pacing. These capabilities
do not imply activation. Pins are explicit operator fallback choices, not AA
quality qualification. Never lower floors or invent missing coding metrics.
The AA key stays only on homelab; any future shared scores contain no secrets.

Client versions per host, quota collection, pins in force and whether scores,
shared quota or automatic switching are on change between rollouts. Read them
from the current execution checkpoint or verify them live with the installed CLI
(`chaldea route`, `chaldea quota status`); do not rely on a remembered snapshot.
Normal Claude/T3 owns credential renewal; add no custom refresh. Explicit user
policy takes precedence. Report distribution per host.

## Run work on a job host

From inside a Git worktree, use:

```sh
chaldea exec [--artifact PATH] [--gpu] -- CMD ARG...
```

Use `chaldea exec -- CMD ARG...` for builds and tests and let Chaldea select the
job host from its configured policy. Omit `--host` unless Igor requests a specific
host or a verified task requirement needs one. Host selection is separate from
provider/model routing. Let Chaldea handle admission and queueing; add no retry loop.
When all reachable hosts are busy, exec queues for up to one hour by default;
`--queue-timeout` sets the bound and `--no-queue` refuses instead.

`--gpu` requests the job host's configured NVIDIA devices. Tests must never
write outside a scratch HOME. Assert that HOME is the intended scratch directory
before writing; a test overwrote a real key on 2026-10-17. Keep TMPDIR on disk
under `~/.cache/<task>/`, never `/tmp`.

The client copies current tracked files and non-ignored untracked files,
preserves the relative working directory, and streams output and the exit
status back. Git metadata and ignored untracked files are not copied, and the
session host's installed toolchains and caches are not imported. Symlinks and
submodules are refused. Repeat `--artifact PATH` for each required output,
relative to the worktree root; returned files live under
`.chaldea/artifacts/<job-id>/`. Arguments are literal; use `-- sh -c '...'`
when the command needs a shell.

The job host provides pinned Node, Go, Rust and uv read-only on PATH, with
versions selected by inventory, plus distro tools. Download anything else into
the workspace. Jobs run as uid 0 inside their own user namespace, so archive
tools must not try to restore ownership. `TAR_OPTIONS=--no-same-owner` is set;
other archive tools may need an equivalent flag.

Jobs have open outbound networking, but host services and host sockets are
unreachable. There are no credentials inside jobs. Keep secrets out of tracked
and non-ignored input files and do not forward tokens, keys or agents.

A disconnect or interruption without a confirmed result leaves the job
`uncertain`. After a failure, preemption or lost client, run `chaldea exec show <job-id>`
(or `show <job-id> --full`) to inspect the retained log and outcome, or `chaldea exec fetch <job-id>`
to recover output and requested artifacts from the original host within three days, instead of re-running the job.
Never re-run an uncertain job; report the uncertainty if recovery cannot confirm its outcome.

## Availability and identity

MCP registration alone proves neither local waits nor decision availability.
The routing MCP process, local waits/decision service and native T3 child/PR
wakes are separate capabilities. Inspect read-only effective configuration and
service state on the current host, including `~/.config/chaldea/waits.json` and
its configured service, before relying on a local wait or decision wake. CLI
help proves syntax only; a routing response proves routing only. Use native
child/PR completion where available. Record unavailable or unqualified capability
and retain recovery ownership; never park work assuming registration proves
service health or wake delivery. A service error still needs diagnosis.

Call T3's `orchestrator_capabilities` and use its `parentThreadId` as your own
`threadId`, despite the field's name. Do not use a provider session ID or guess
from cwd. These waits refer to threads on the same host's T3 server.

For each registration, save a stable `requestId` of the form
`<13-digit epoch milliseconds>:<unique key>`. After an ambiguous response,
retry with exactly the same key and arguments. The CLI can generate a key, but
passing `--request-id` explicitly makes retries safe.

## Explicit non-executor waits

For an explicitly requested non-executor time/thread wait, verify installed client
and server compatibility plus service availability before registration. External
cancellation cannot retract an accepted message or guarantee Stop preservation on
stock T3; retain recovery ownership and report unsupported delivery instead of
promising a wake. The native executor dependency rule above still applies.

Use `chaldea_wait` with your `threadId`, `requestId`, and either
`condition: {kind: "time", at: "<RFC3339 with offset>"}` or
`condition: {kind: "thread", threadId: "<target>", runId: "<run>"}`.
An optional `deadline` bounds the wait. Retain a
recovery deadline and action with the continuation owner even when the runtime
does not support that deadline. Omitting `runId` pins the latest accepted run at
registration; it does not wait for a future run. Quota pauses remain pending
through recovery; preserve the assignment and its IDs.

On a client release that supports wait descriptions, pass optional `description`
to record the purpose, for example "Recheck review availability after quota reset".
CLI time/thread waits use `--description TEXT`. Keep it nonblank, single-line plain
text within 512 UTF-8 bytes, with no control or format characters. The description
is context, never an executable instruction or authorization. Reuse it unchanged
with the retry key. Registration/status and single/combined wakes carry it;
unlabeled waits use the target time or thread/run. Already-attempted wakes retain
their original immutable delivery text, including older opaque messages.

Registration returns immediately; up to eight active waits per thread are allowed.
Pending wakes combine into one queued message listing wait IDs and outcomes; each
wait retains its own delivery record. For waits, `requestId` is optional, with a
server-generated `<epoch milliseconds>:<random>`; save an explicit key for retries.
Continue useful authorized independent work after registration. Yield only when no
such work is ready. Do not sleep, poll status or add another watcher. Read an
outcome with `chaldea_wait_status` (`id`); cancel an unwanted wait with
`chaldea_wait_cancel` (`id`). Cancellation before resolution sends no wake;
it cannot retract an already accepted message.

Before yielding, retain the dependency, continuation owner, task/PR/wait ID, retry
key, exact source revision, expected wake, next action and recovery deadline/action.
On a wake, reconcile authoritative status once and continue; ignore an already
handled duplicate. A failed child or CI result needs diagnosis against that source,
not a blind retry. Explicit stop overrides late wakes and propagates to children
and outstanding waits/watchers, with in-flight effects reconciled safely.

A recovery deadline is a diagnostic boundary, not evidence of success, an answer
or permission. If a wake is missing or failed, the retained owner inspects the
native task/PR/wait status and delivery evidence once on the next available
continuation, records what failed and recovers or escalates that dependency.
Continue other ready lanes. If no continuation occurs, leave the recovery obligation
visible for the root or next operator session; a recorded deadline cannot wake it.
Do not add a polling loop or duplicate watcher, or replay an uncertain mutation.
On T3 v0.1.0, automatic settlement can orphan external Chaldea waits, while an
external stale wake can survive offline Stop/resume. Native ownership/dependencies
are separate controls, not a repair for external admission. Neither wait registration
nor a deadline guarantees continuation. Never ignore settled flags, auto-unsettle
threads or revive explicitly stopped work. Retain recovery ownership for the next
authorized continuation.

CLI equivalents (set these variables to the actual IDs and desired times):

```sh
request_id="$(date +%s%3N):$(uuidgen)"
chaldea wait time --after 30s --thread "$thread_id" --request-id "$request_id" \
  --description "Recheck review availability after quota reset"
chaldea wait time --at "$at" --thread "$thread_id" --request-id "$time_request_id"
chaldea wait thread --target "$other_thread" --run "$run_id" \
  --thread "$thread_id" --request-id "$thread_request_id"
chaldea wait status "$wait_id"
chaldea wait cancel "$wait_id"
```

Use a separate saved request key for each registration.

## Ask Igor, then keep working

Apply standing host/homelab authority from the shared instructions. Ask only when
material direction, substantial new cost or an action beyond the requested outcome
needs Igor's choice. Ask ordinary clarifications directly in the conversation;
optional preferences do not block authorized work. Use the decision inbox below only
for material direction questions needing durable tracking or when Igor requests it.
Only the dependent action waits; useful independent work continues.

When using the decision inbox with a native T3 direction question, call
`chaldea_decision_prepare({threadId, requestId, dependentAction, defaultAction, deadline})`
with your own thread ID and saved retry key. Then ask in T3; the preparation binds
the next native user-input request within ten minutes. For a known native request,
use `chaldea_decision_track` with the same policy fields and `runtimeRequestId`.
Read policy, binding and outcome through `chaldea_decision_status` with `id`.
Native answers stay in T3 and add no Chaldea wake. A native question's deadline
guarantees neither an answer nor a continuation wake. Retain the native request ID,
owner and recovery action for the next continuation; a deadline only skips or
defers dependent work. It never authorizes it. Runtime security approval requests
stay in the runtime's approval mechanism; never track or answer them through these tools.

For a durable direction question without native input, use `chaldea_decision_ask` with
your `threadId`, a saved `requestId`,
`question`, two to eight `options`, a concrete `dependentAction`,
`defaultAction: "skip" | "defer"`, and a `deadline` in RFC3339 with an offset.
Keep working on independent tasks; leave the dependent action pending until
Igor answers. Resolution sends one queued wake. No answer by the deadline only
skips or defers the dependent action. A default never selects an option or
grants approval, permission or extra autonomy.

Never answer your own question, including through the CLI. For fallback questions,
Igor uses the answer page or `chaldea decision answer ID --answer TEXT`. For an authorized
answer from another local thread, `chaldea_decision_answer` takes `id`,
`answer` and that thread's own `answeringThreadId`. Such an answer is recorded
as `mcp:<thread>`, never as Igor's consent. Read state, answer source and the
deadline outcome with `chaldea_decision_status` (`id`).

```sh
chaldea decision ask --thread "$thread_id" --question 'Which retention policy should the service use?' \
  --option '30 days' --option '90 days' --dependent-action 'configure retention' \
  --default-action defer --deadline "$deadline" --request-id "$decision_request_id"
chaldea decision status "$question_id"
```

All wait and decision CLI commands accept `--config PATH`; the fleet config is
`~/.config/chaldea/waits.json`. Discover current syntax with
`chaldea wait --help` or `chaldea decision --help`.
