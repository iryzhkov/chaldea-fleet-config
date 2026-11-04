# Installed fleet tools skill

Converge renders `fleet-tools/SKILL.md` after all installers finish. Claude reads
`~/.claude/skills`, OpenCode and Codex share `~/.agents/skills`, and Codex also
gets `~/.codex/skills`. The renderer checks the homelab-cli launchers selected
by the agent_tools install list, plus the installed Chaldea path;
override `agent_config_fleet_tools_directories` and
`agent_config_fleet_tools_executables` for additional custom tools. No PATH scan
or service command is used. Each included tool receives only `--describe`, with
closed stdin and a five-second timeout. Missing tools are absent; a failed,
malformed or timed-out description becomes "description unavailable".

The compact JSON convention is
`{name, summary, help, commands: [{name, summary, access}]}`.
Summaries are one line, help is `TOOL --help`, and access is `read` or
`write`. Use `(default)` for an unnamed command. Any state change, including
lifecycle operations, credential caches, retention touches and maintenance,
is write; classify mixed commands conservatively. Discovery must exit before
configuration, credentials, telemetry and backend dispatch.

The default interactive operator sees all installed commands and the one-line
OV pointer. Hosts that register Jocasta also grant its WebMCP pointer through
their host profile. The legacy Jocasta CLI is not part of the default agent
index. Replace the complete profile object for restricted sessions:

```yaml
agent_config_fleet_tools_profile:
  name: restricted-reader
  tools:
    feed: [read]
    pve: [read]
  mcp: [ov-memory]
```

Unlisted tools and access classes are hidden. An explicit empty grant overrides
a wildcard. `tools: {}` and `mcp: []` produce an empty index. Invalid profiles
fail closed: an empty index replaces previous instructions before converge fails.
These grants filter instructions; actual command authorization
remains the session/runtime's responsibility. This is a converge-time profile,
not automatic T3 session-profile detection. A future session launcher must pass
its grants and use an isolated skill destination when profiles run concurrently.

Generated output is deterministic, grouped by area, with one line per tool and
granted command names grouped by access. The current tool inventory fits below
60 lines. Full help can include additional commands; it grants no authority.
Check mode skips installed probing and output writes, because prerequisite
installers may only be simulated.

## Akasha report client pin

The inventory selects homelab-cli601d226867238a5e3d9150f09aa5bf4ed7fba06c
for the report pagination fix. PR46 must merge and pass CI before publishing
this fleet selection. Its production delta from6d17c5f changes only the Akasha
request limit and response row bound from100 to1000.

The cumulative delta from the former f035d282 pin also contains HoloNet and
observer Go service sources, removal of retired feedd/toolfeedback service
sources, help corrections in feed/toolfeedback and a help-only SIGPIPE fix in
docker-update-sweep. The canonical agent_tools role clones sources, installs
the unchanged OV dependency lock/launcher and links its existing command list.
It neither builds nor enables the new Go services and does not run install.sh.
The shared shell/Python libraries, jobs and installer are unchanged. No new
service, MCP configuration, access helper, permission or credential is selected.

Changing the common pin changes the content-derived agent_tools release on all
six inventory hosts at their next agent_tools run, including timer-driven pulls
after publication. The OV source refs remain unchanged, but its venv is rebuilt
beside the previous release. Stage the canonical role on omarchy-pc first and
prove the full30day Akasha report before allowing fleet pulls to advance. Keep
the previous complete agent-tools release for rollback. A check run reports
the build; it cannot prove a private Git fetch, dependency install or live report.
Use site.yml with the existing identity guard and --tags agent_tools through
the canonical pull path. Review CHECK, then REAL and a second run with changed=0;
never copy a script or repoint an installed symlink by hand.

## Release and pin handoff

No release or host converge is part of this change. Merge the homelab-cli,
Jocasta and Chaldea source PRs after accepted review and CI. Publish the normal
agent-tools release/source pin containing the new homelab-cli commit in
`agent_tools_sources` in `inventory/group_vars/all/main.yml`. Jocasta is not built by
that role: publish/install its reviewed CLI through its owning deployment workflow
(currently documented as UpKeeper). Pin the reviewed Chaldea app commit via its
owning deployment workflow. Do not
point hosts at a development checkout or copy individual scripts: homelab-cli's
bin and shared library must travel together. Then merge/converge this renderer
on one approved host, inspect its generated skill and compare a second
converge for idempotency before distributing further.
