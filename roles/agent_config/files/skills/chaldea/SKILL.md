---
name: chaldea
description: >-
  Use Chaldea for builds, tests and heavy runs on fleet job hosts, durable time
  or thread waits, and questions in Igor's decision inbox. Reviews and worker
  briefs belong to review-delegation.
---

# Chaldea in T3 sessions

Chaldea adds fleet compute, durable waits and a decision inbox to T3. Keep using
T3's native delegation completion and `watch_pull_request` for child tasks and CI;
use the `review-delegation` skill for reviews.

Restart T3 with `chaldea t3 restart`, never with `systemctl` directly.

## Route before delegating

Call `chaldea_route` or `chaldea route --role ROLE` before each T3 `delegate_task`.
Roles are `builder`, `critical-review`, `bulk-read` and `general`. Pass the returned
`providerInstanceId`, `model` and `options` as the delegate target. Chaldea recommends;
T3 launches the child. An explicit session model restriction still applies.

For reviews, supply the writer's driver as `authorProvider`, `claudeAgent` or `codex`,
or CLI `--author-provider`, so routing requires the other provider. Main diff reviews
use `builder` to retain the Opus/Sol pair; consequential design or disputed findings
use `critical-review` for Fable/Astra. If the tool or CLI cannot recommend a target,
use the shared CLAUDE.md model roles and keep reviews on the other provider.

Model roles: Opus 5.5 or Sol 6.1 high for builders, Fable 5.1 or Astra medium
for critical review, Haiku 5.5 or Luna 6 medium for bulk reading, and Opus 5.5
or Sol 6.1 medium for general work, or whatever `chaldea route` recommends.
Sonnet-family models are excluded. Haiku is allowed. Never use max, ultra,
ultrathink or ultracode. Respect explicit session restrictions.

With the role-target client, routing evaluates the live T3 catalog against
Artificial Analysis floors and objectives, Slopalytics probation and quota pacing.
Fleet pins override model policy. Until its score snapshot is configured, the
fallbacks above apply. The AA key exists only on homelab. Router hosts read
non-secret snapshots through authenticated Akasha grants. See Chaldea's
docs/route.md for the snapshot and probation settings. Older clients keep fixed
pairs until upgraded, so apply this policy's Sonnet exclusion explicitly.

The Slopalytics URL is https://slopalytics.com/data/t3-usage.json. Fleet renders
pacing and capacity thresholds; Claude usage collection stays off until Igor
approves it and its local account binding is verified.

## Run work on a job host

From inside a Git worktree, use:

```sh
chaldea exec [--host H] [--artifact PATH] [--gpu] -- CMD ARG...
```

Use `chaldea exec` for builds and test suites instead of running them on omarchy-pc,
Igor's gaming PC. `--host` is optional: without it, `~/.config/chaldea/exec-hosts`
tries agent-a, agent-b, omarchy-pc when its game gate allows, then laptop when awake.
It moves on only after a refusal or an unreachable host before the request was sent.
Hosts run several jobs concurrently: agent-a 3, omarchy-pc 2, agent-b 1 and laptop 1; when all reachable hosts are busy, exec queues for up to one hour (--queue-timeout, --no-queue to refuse), so never add a retry loop.

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

Waits and the decision inbox are deployed on **omarchy-pc only** until rolled
out elsewhere. A session can tell they are configured when the `chaldea` MCP
server is registered; do not assume availability on another host or from the
CLI alone. A service error still needs diagnosis.

Call T3's `orchestrator_capabilities` and use its `parentThreadId` as your own
`threadId`, despite the field's name. Do not use a provider session ID or guess
from cwd. These waits refer to threads on the same host's T3 server.

For each registration, save a stable `requestId` of the form
`<13-digit epoch milliseconds>:<unique key>`. After an ambiguous response,
retry with exactly the same key and arguments. The CLI can generate a key, but
passing `--request-id` explicitly makes retries safe.

## Wait without sleeping or polling

Use `chaldea_wait` with your `threadId`, `requestId`, and either
`condition: {kind: "time", at: "<RFC3339 with offset>"}` or
`condition: {kind: "thread", threadId: "<target>", runId: "<run>"}`.
An optional `deadline` bounds the wait. Omitting `runId` pins the latest accepted
run at registration; it does not wait for a future run. Quota pauses remain
pending through recovery.

Registration returns immediately; up to eight active waits per thread are allowed, and pending wakes combine into one queued message listing every wait ID and outcome while each wait retains its own delivery record. For waits, `requestId` is optional (the server generates `<epoch milliseconds>:<random>`); save an explicit key for idempotent retries, then end the turn when ready. Do not sleep,
poll status or add another watcher. Read an outcome with `chaldea_wait_status`
(`id`); cancel an unwanted wait with `chaldea_wait_cancel` (`id`). Cancellation
before resolution sends no wake; it cannot retract an already accepted message.

CLI equivalents (set these variables to the actual IDs and desired times):

```sh
request_id="$(date +%s%3N):$(uuidgen)"
chaldea wait time --after 30s --thread "$thread_id" --request-id "$request_id"
chaldea wait time --at "$at" --thread "$thread_id" --request-id "$time_request_id"
chaldea wait thread --target "$other_thread" --run "$run_id" \
  --thread "$thread_id" --request-id "$thread_request_id"
chaldea wait status "$wait_id"
chaldea wait cancel "$wait_id"
```

Use a separate saved request key for each registration.

## Ask Igor, then keep working

Before asking Igor through native T3 user input, call
`chaldea_decision_prepare({threadId, requestId, dependentAction, defaultAction, deadline})`
with your own thread ID and saved retry key. Then ask in T3; the preparation binds
the next native user-input request within ten minutes. For a known native request,
use `chaldea_decision_track` with the same policy fields and `runtimeRequestId`.
Read policy, binding and outcome through `chaldea_decision_status` with `id`.
Native answers stay in T3 and add no Chaldea wake. Never track or answer permission
or approval requests through these tools.

For providers without native input, use the fallback `chaldea_decision_ask` with
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
chaldea decision ask --thread "$thread_id" --question 'Run the dependent step?' \
  --option Defer --option Run --dependent-action 'run the dependent step' \
  --default-action defer --deadline "$deadline" --request-id "$decision_request_id"
chaldea decision status "$question_id"
```

All wait and decision CLI commands accept `--config PATH`; the fleet config is
`~/.config/chaldea/waits.json`. Discover current syntax with
`chaldea wait --help` or `chaldea decision --help`.
