# chaldea-fleet-config

The [Chaldea client role](docs/chaldea-client.md) manages pinned client releases, migration, quota and waits user services, and the explicit Codex balance binding. Activation waits for the first published client release.

Restricted fleet compute roles are opt-in. See [job-host enrollment, policy, quotas and exact apply steps](docs/job-host.md).

Ansible configuration for the Chaldea hosts. Each host converges itself with
`ansible-pull` from this repository on a systemd user timer: there is no
controller and no SSH between hosts. Nothing here adds a step to an agent
session; it only keeps the tools and shared files those sessions use in place.

`site.yml` applies these roles to the host it runs on:

- `agent_tools`: homelab-cli and the ov-memory MCP server, built into
  `~/.local/share/agent-tools/<release>` with a `current` symlink and links in
  `~/.local/bin`. Neither tool publishes releases, so each is pinned to an exact
  commit and the release name is a hash of the pins.
- `agent_config`: the shared instruction files (`~/.claude/omarchy-setup/CLAUDE.md`,
  `~/.codex/AGENTS.md`, `~/.config/agents/*.md`), the fleet's own skills under
  `~/.claude/skills` and `~/.agents/skills`, and the OpenCode wrapper. Per-host
  files such as `~/.claude/CLAUDE.md` and `~/.claude.json` are not managed, and
  neither are skills installed by the skills CLI (caveman, find-skills, the
  mattpocock skills, recorded in `~/.agents/.skill-lock.json`) or the skills
  Omarchy links in; those stay with whatever installed them.
- `mise_agents`: keeps selected tools without a user declaration at their
  newest release that is at least 24 hours old. Defaults remain claude, codex
  and the existing OpenCode declaration (`npm:@opencode/cli`). A drop-in,
  `~/.config/mise/conf.d/agents.toml`, lists fleet-owned tools as `latest`;
  the play installs the newest release old enough. User-declared tools are
  omitted from both declaration and installation, preserving their complete
  versions, options and `allow_builds`. See [mise ownership](docs/mise-agents.md).
  The drop-in holds plain version strings because options there need
  `mise trust`, which for that directory trusts the whole home directory.
- `huyang`: opt-in pinned releases, safe checkout migration and a separate
  checksum-pinned Neovim/parser/language-server toolchain. Every host is disabled
  until the orchestrator enables it. See [activation and rollback](docs/huyang.md).
- `mcp_registrations`: registers the fleet's own MCP servers, huyang and
  ov-memory, with Claude Code (user scope, through `claude mcp get`,
  `claude mcp remove` and `claude mcp add-json`; `~/.claude.json` is never
  edited directly) and with Codex (only the `[mcp_servers.<name>]` tables of
  `~/.codex/config.toml`). It removes any `local-file-llm` registration and
  leaves every other server alone. Diffs never show environment values.
  Remote servers may use native OAuth through `mcp_registrations_remote_servers`.
  The interactive `jocasta` selections for laptop, agent-a, agent-b and
  omarchy-pc use the [managed native helper](docs/managed-interactive-webmcp.md)
  with Claude and Codex. Ordinary OpenCode uses the
  [separate helper plugin](docs/opencode-interactive-jocasta.md), selected only
  on the qualified laptop. Other hosts remain unselected until their own staging
  and native checks pass. Role defaults remain off. The
  [three-host staging sequence](docs/managed-interactive-three-hosts.md) describes
  protected managed-helper delivery for Claude and Codex.
  Merging selections can activate them through ordinary pull timers; each host
  still requires its own native-client acceptance. Public OAuth remains supported
  for explicitly selected entries. The module compares only the named entry's
  public fields in `~/.claude.json` and changes Claude registration through its CLI.
- `t3`: asserts that T3 runs the pinned version and its user service is active.
  It upgrades only when `t3_allow_upgrade=true` is passed, because `t3 update`
  restarts the service and interrupts running sessions. After the pin/service
  assertions and earlier roles succeed, a pull checks GitHub's latest stable
  release and writes installed/pinned/latest versions and discovery status directly
  to the local journal under tag `chaldea-t3-release`, including unavailable
  lookups. The existing four-hour timer supplies unattended checks with the UI
  closed; discovery does not install or restart T3. Check mode makes no release request. Set
  `t3_update_check_enabled: false` to disable discovery.
- `data_disk`: on hosts with `data_disk_root`, keeps T3 worktrees, `~/.cache/tmp`
  and the Go build cache on the data disk. It refuses to run unless a filesystem
  is mounted exactly at `data_disk_root` (optionally of `data_disk_fstype` and
  `data_disk_uuid`), and unless each of those paths is absent or already the
  right link.
- `retention`: the `chaldea-retention` script and its daily timer, with explicit
  bounds: T3 worktrees within 20G (clean worktrees untouched for 14 days go, and
  3 days when over budget), `~/.cache/tmp` entries older than 3 days, the Go
  build cache within 10G (so the first run may clean a large existing cache),
  and `mise prune`. Anything a process holds or that changed in the last 24
  hours is kept, and so is any worktree with uncommitted changes, commits no
  branch contains, or ignored files other than regenerable output directories
  (`retention_disposable_ignored`: `node_modules`, `target`, `.venv` and the
  like). A worktree is moved into a trash directory and checked again before
  git removes it. `mise prune` never removes the version a tool's `latest`
  link points at, which is the one T3 launches, or one a process runs from.
- `pull_timer`: the `chaldea-fleet-pull` timer that runs `ansible-pull` every
  four hours with a pinned ansible-core.

Hosts and their switches are in `inventory/hosts.yml`; pins shared by every host
are in `inventory/group_vars/all/main.yml`. A large reviewed host activation may
live in its own `inventory/host_vars/HOST/` file instead of inline, such as the
laptop's Jocasta tooling sessions (docs/chaldea-client.md). No secret is stored here: credential files
are listed by path, and the play only checks that each exists and is private.

## Private repositories

This repository is public; homelab-cli is private. The existing pull URLs use SSH
with a read-only deploy key per repository, behind a Host alias in
`~/.ssh/config`: `github-chaldea-fleet-config` (`pull_timer_repo`) and
`github-homelab-cli` (`agent_tools_homelab_cli_repo`). The play checks that each
alias is defined and stops if one is missing; it never creates or reads the keys.

## Enrolling a host

1. Add the host to `inventory/hosts.yml` under `agent_hosts` or `servers`, with
   `expected_hostname` set to the output of `hostname` on it (the play refuses to
   apply an entry to any other machine) and `data_disk_root` if it has one.
2. On the host, create a read-only deploy key for each private repository, add
   it to that repository on GitHub, and add its Host alias:

   ```
   Host github-chaldea-fleet-config
     HostName github.com
     User git
     IdentityFile ~/.ssh/deploy-chaldea-fleet-config
     IdentitiesOnly yes
   ```

   and the same for `github-homelab-cli`.
3. Install the pinned ansible-core:

   ```sh
   python3 -m venv ~/.local/share/chaldea/ansible-core-2.19.14
   ~/.local/share/chaldea/ansible-core-2.19.14/bin/pip install ansible-core==2.19.14
   ```

4. Run in check mode and read the diff. This clones the repository into
   `~/.local/share/chaldea/fleet-config` but changes nothing else:

   ```sh
   ~/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-pull \
     --url git@github-chaldea-fleet-config:iryzhkov/chaldea-fleet-config.git --checkout main \
     --directory ~/.local/share/chaldea/fleet-config \
     --limit HOST --check --diff site.yml
   ```

5. Run the same command without `--check --diff` to converge.

From a clone of this repository, `ansible-playbook site.yml --limit HOST --check
--diff` does the same check against your working tree.

## Enabling the timers

Both timers are installed disabled. To enable them for a host, set
`pull_timer_enabled: true` (and, after reviewing `chaldea-retention --dry-run` on
that host, `retention_timer_enabled: true`) under the host in
`inventory/hosts.yml`, merge, and converge once by hand. Setting a variable back
to false stops and disables its timer on the next run, whether it was enabled or
only started by hand.


## Timer outcomes

The pull and retention services run through `chaldea-timer-report`. Every run
has one local outcome, keyed by systemd's invocation ID, in
`~/.local/state/chaldea/fleet-status.json` (the last 50 outcomes, capped at
128 KiB, atomically replaced, mode 0600). Each outcome is also written as one
JSON line to its service journal. The local record's `delivery` field shows
the final delivery result; the journal line is written before attempting the
feed and therefore says `pending`.

A successful run with changes posts one short `info` entry: host, changed
count, and current release names for pull, or removed tool versions for
retention (at most 12 names, with a count of omitted names). Pull counts Ansible's changed tasks; retention counts successful
deletions, cache cleans and interrupted-worktree restorations. A successful
run with no changes posts **nothing** to the feed; its local/journal outcome
is `unchanged`. Failures post one `fail` entry with the failing task name and
a fixed, short reason (for example, module exit status, budget exceeded or
systemd timeout). No module messages, command output, arguments or environment
values are sent to the feed or status file. Task-name template expressions
are redacted. Timer child output is suppressed; run the command manually for
interactive diagnosis.

Temporary cleanup remains best-effort: it attempts all removable contents of
each old entry, including trees containing read-only Go modules. Leftover
entries produce one aggregate, non-failing note per run in local status and
the journal, without recording paths or posting a warning to the feed.
Disappearing entries are skipped. Worktree, temporary-file, Go-cache and mise
stages run independently; an error in one does not skip the others. A nonzero
`go clean -cache` exit makes the run fail at `prune Go cache` and does not count
a successful cache clean; the mise stage is still attempted.

`OnFailure=chaldea-timer-failure@…` covers startup failures, crashes, OOM kills
and the one-hour execution timeout. The wrapper handles ordinary completion;
the handler uses `MONITOR_INVOCATION_ID` to deduplicate the same failure.
This requires systemd 251 or newer. Both services use the same safe summary
format. An Ansible run that succeeds without producing its callback summary
is reported as a failure, rather than silently claiming no changes.

The reporter checks for a readable, nonempty feed key at
`~/.config/feed/key` (respecting `XDG_CONFIG_HOME` and `FEED_KEY_FILE`), or
`FEED_TOKEN`, before invoking `feed post`. No credential means no request.
Feed attempts have an eight-second deadline, kill descendants on timeout,
never retry, and never change the job's exit status. A failed/refused request
stays in local status; the reporter does not install credentials. The local
claim is written before posting, so a crash or ambiguous HTTP timeout never
causes a duplicate POST; it may leave `delivery=pending` or `feed-timeout`
when acceptance by the server is unknown. There is no replay queue.

Read outcomes with:

```sh
feed recent --source chaldea-fleet --full
feed recent --source chaldea-retention --full
python3 -m json.tool ~/.local/state/chaldea/fleet-status.json
journalctl --user -u chaldea-fleet-pull.service -u chaldea-retention.service \
  -u 'chaldea-timer-failure@*' --since today
```

Read-only authentication checks on 2026-10-16 found a usable credential on
omarchy-pc and laptop (an authenticated feed read succeeded). Agent-a and
agent-b have no key, so they record outcomes locally and in the journal
without contacting the feed. No test entries were posted. An authenticated
read verifies the shared credential; it does not exercise the POST endpoint.

Before enabling retention, run `chaldea-retention --dry-run` and read every
candidate. It prints worktree and temporary-entry deletion sizes in bytes,
the Go cache size when a clean is planned, and each prunable mise version's
installed size. Mise download caches are excluded from those size estimates.
Dry-run mode does not delete or restore worktrees, clean caches or uninstall
tools. Timer reporting is installed on the next manual convergence; this PR
does not deploy it or enable timers.

## CI

CI runs on GitHub-hosted `ubuntu-24.04` runners, because this repository is public
and a self-hosted runner would execute pull requests from forks on a fleet host.
Python 3.13 comes from a pinned `actions/setup-python`. The workflow stages Node 26.12.0 for Linux x64 from the official Node
archive, verifies its pinned SHA-256 before extraction or execution, and adds its
absolute bin path to the job PATH. The archive pin matches the reviewed job-toolchain
pin in `inventory/group_vars/all/main.yml`; update both deliberately when changing it.
Node lives only in that run's disk-backed `TMPDIR` and is removed by the existing
always-run cleanup. This does not install Node on the host. The runner still needs
`curl`, `sha256sum`, `tar` with xz support, and the existing Python/venv prerequisites.
For direct `tools/ci.sh` runs, supply Node on PATH; the script fails early if absent.

`bash tools/ci.sh` runs every gate locally and in CI: it builds a virtualenv from
the hashed lock `requirements-ci.txt`, then runs the unit tests, `ansible-lint`,
a syntax check and a `--check --diff` run for the synthetic host in
`tests/synthetic-inventory.yml`, whose home is a scratch directory in the
checkout. It then converges that scratch home twice, without `agent_tools` and
`t3`, and fails if the second run changes anything, and runs the role tests
`tests/user_timer.yml` and `tests/data_disk.yml`. Every run uses the fake
`systemctl` in `tests/fake-bin` and the fake `claude` in `tests/fake-claude`,
so CI never touches the runner's own user services or agent configuration. To
change a CI dependency, edit `requirements-ci.in` and regenerate the lock with
the command at the top of `requirements-ci.txt`.
