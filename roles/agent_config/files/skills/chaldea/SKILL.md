---
name: chaldea
description: >-
  Use Chaldea for builds, tests and heavy runs on fleet job hosts.
  Reviews and worker briefs belong to review-delegation.
---

# Chaldea in T3 sessions

Chaldea adds fleet compute to T3. Keep using
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
Chaldea moves to another host only after a refusal or an unreachable host before
submission; recover an uncertain submitted job before considering another run.
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

## Ask Igor, then keep working

Apply standing host/homelab authority from the shared instructions. Ask only when
material direction, substantial new cost or an action beyond the requested outcome
needs Igor's choice. Ask ordinary clarifications directly in the conversation;
optional preferences do not block authorized work. Ask material direction questions
the same way. Only the dependent action waits; useful independent work continues.
Runtime security approval requests stay in the runtime's approval mechanism.
Never answer your own question. A deadline or unanswered question never grants
permission; it only leaves the dependent action deferred.
