# chaldea-fleet-config

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
- `mise_agents`: keeps claude, codex and OpenCode (`npm:@opencode/cli`) at
  their newest release that is at least 24 hours old. A drop-in,
  `~/.config/mise/conf.d/agents.toml`, lists each as `latest`, and the play
  installs the newest version old enough; mise runs the newest installed
  version. The user's `~/.config/mise/config.toml` is never written, and a tool
  also listed there takes that file's version; the play reports it. The drop-in
  holds only plain version strings, because a drop-in with tool options needs
  `mise trust`, which for that directory trusts the whole home directory.
- `mcp_registrations`: registers the fleet's own MCP servers, huyang and
  ov-memory, with Claude Code (user scope, through `claude mcp get`,
  `claude mcp remove` and `claude mcp add-json`; `~/.claude.json` is never
  edited directly) and with Codex (only the `[mcp_servers.<name>]` tables of
  `~/.codex/config.toml`). It removes any `local-file-llm` registration and
  leaves every other server alone. Diffs never show environment values.
- `t3`: asserts that T3 runs the pinned version and its user service is active.
  It upgrades only when `t3_allow_upgrade=true` is passed, because `t3 update`
  restarts the service and interrupts running sessions.
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
are in `inventory/group_vars/all.yml`. No secret is stored here: credential files
are listed by path, and the play only checks that each exists and is private.

## Private repositories

This repository and homelab-cli are private. Each host reads them over SSH with
its own read-only deploy key per repository, behind a Host alias in
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

## CI

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
