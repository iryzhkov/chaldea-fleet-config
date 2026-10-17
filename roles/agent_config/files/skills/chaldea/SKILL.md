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

## Run work on a job host

From inside a Git worktree, use:

```sh
chaldea exec --host H [--artifact PATH] [--gpu] -- CMD ARG...
```

Use this for builds, tests and heavy runs on `agent-a`. Use `omarchy-pc` only
when no Steam game or Minecraft is running; its idle policy can refuse or
preempt a job. `--gpu` requests the job host's configured NVIDIA devices.

The client copies current tracked files and non-ignored untracked files,
preserves the relative working directory, and streams output and the exit
status back. Git metadata and ignored untracked files are not copied, and the
session host's installed toolchains and caches are not imported. Symlinks and
submodules are refused. Repeat `--artifact PATH` for
each required output, relative to the worktree root; returned files live under
`.chaldea/artifacts/<job-id>/`. Arguments are literal; use `-- sh -c '...'`
when the command needs a shell.

Jobs have open outbound networking, but host services and host sockets are
unreachable. There are no credentials inside jobs. Keep secrets out of tracked
and non-ignored input files and do not forward tokens, keys or agents.

A disconnect or interruption without a confirmed result leaves the job
`uncertain`. Never re-run an uncertain job. Inspect the reported journal entry
under `~/.local/state/chaldea/exec/journal/` and report the uncertainty. A
definitive refusal or preemption is recorded separately.

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

Registration returns immediately. End the turn after registering a wait;
exactly one marked queued wake message arrives when it resolves. Do not sleep,
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

Use `chaldea_decision_ask` with your `threadId`, a saved `requestId`,
`question`, two to eight `options`, a concrete `dependentAction`,
`defaultAction: "skip" | "defer"`, and a `deadline` in RFC3339 with an offset.
Keep working on independent tasks; leave the dependent action pending until
Igor answers. Resolution sends one queued wake. No answer by the deadline only
skips or defers the dependent action. A default never selects an option or
grants approval, permission or extra autonomy.

Never answer your own question, including through the CLI. Igor uses the
answer page or `chaldea decision answer ID --answer TEXT`. For an authorized
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
