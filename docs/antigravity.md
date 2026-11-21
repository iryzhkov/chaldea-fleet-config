# Antigravity CLI and T3

The fleet manages mise tool `antigravity-cli` (executable `agy`) alongside
Claude, Codex and OpenCode. The mise registry selects
`aqua:google-antigravity/antigravity-cli`. Aqua maps amd64 to x64 and leaves
arm64 intact; release 1.5.13 supplies both `agy_cli_linux_x64.tar.gz` and
`agy_cli_linux_arm64.tar.gz`. This confirms archive availability, not an
arm64 execution qualification. User-declared versions retain mise ownership.

Antigravity can replace the binary inside a mise install through self-update.
Managed blocks in `~/.bashrc` and `~/.zshrc` export
`AGY_CLI_DISABLE_AUTO_UPDATE=true` for new interactive shells. The exact value
is `true`, not `1`. This avoids mise [env] fragments, which require trusting
the home directory. No equivalent settings.json key was found in the inspected
1.5.13 binary or the settings reference. Existing shells need to reload their
startup file. Other launch environments must supply the variable themselves.

The CLI receives the maintained `agents/AGENTS.md` at `~/.gemini/AGENTS.md`
and guarded skill copies under `~/.gemini/config/skills`. There is no second
guidance source. A user-owned GEMINI.md is left alone; agy loads both names.
The fleet-tools generated skill also installs at this destination.

Fleet stdio registrations use `~/.gemini/config/mcp_config.json` and its
`mcpServers` map. The module preserves unrelated entries and top-level values,
removes retired fleet names, redacts environment values, supports check mode
and refuses invalid or symlinked files. It accepts comments and trailing commas;
a changed file is serialized as plain JSON. A scratch
1.5.13 probe confirmed that stdio children inherit DBUS_SESSION_BUS_ADDRESS,
XDG_RUNTIME_DIR and HUYANG_SOCKET from the CLI's environment, so no values
from the converging Ansible process are captured in configuration.

## Fleet web MCP servers

Antigravity gets the managed Jocasta, full OV (`ov`) and Shizune servers on
the hosts where Claude and Codex have them: Jocasta on laptop, agent-a,
agent-b and omarchy-pc; `ov` and `shizune` on laptop and omarchy-pc. Each host
opts in by listing `antigravity` in that server's `providers` in its
`mcp_registrations_remote_servers`. The `ov` and `shizune` entries there carry
only `name` and `providers`; their own enable flags still select them.

agy 1.5.13 cannot use the managed headers helper directly. Its HTTP server
configuration (`serverUrl` or `url`) accepts only static `headers`, OAuth with
a registered client (`oauth.clientId`/`clientSecret`) or Google credentials
(`authProviderType`). `agy mcp add --help` and the strings in the binary show
no header-helper or command field. A static header would put a token in
`mcp_config.json`, and OAuth would need a new Authentik client, so neither is
used.

Instead the module writes a stdio entry that runs the root-owned bridge
`/usr/local/libexec/webmcp-stdio-bridge` with exactly two arguments, the
server name and the inventory host, for example
`{"command": "/usr/local/libexec/webmcp-stdio-bridge", "args": ["jocasta", "omarchy-pc"], "env": {}}`.
The webmcp_interactive role installs the bridge from
`roles/webmcp_interactive/files/webmcp-stdio-bridge`. The bridge:

- accepts only the fixed tuples jocasta on the four managed hosts, and ov and
  shizune on laptop and omarchy-pc; anything else exits with status 2;
- forwards each JSON-RPC line from stdin to that server's fixed HTTPS URL
  (Streamable HTTP: JSON or Server-Sent Events replies, `Mcp-Session-Id`,
  `MCP-Protocol-Version`, and a DELETE of the session at exit);
- gets `Authorization` from the same helper tuple Claude and Codex use
  (`jocasta HOST`, `ov-full HOST`, `shizune HOST`), run with an empty
  environment, so the helper's own host and UID binding applies unchanged;
- keeps the header in memory for at most 60 seconds, asks the helper again
  after a 401, and never writes a header or token to disk, argv, stdout or
  stderr;
- ignores proxy environment variables, refuses redirects and uses the system
  trust store.

The bridge is a per-session child of agy, not a daemon, and it holds no
credential of its own. It does not forward server-initiated messages on a
separate GET stream, so list-changed notifications are not delivered; replies
to requests are. If the upstream session expires, the bridge answers with
error -32001 and agy has to reconnect the server.

Disabling `webmcp_interactive_enabled` makes the role fall back to the OAuth
definitions, which Antigravity has no form for; its entries are skipped, not
removed. Set a server's `state: absent` to remove it.

## T3

T3 runs the agy CLI as its Antigravity ACP runtime with a private
per-instance GEMINI_HOME under `~/.t3/userdata/providers/antigravity/<id>`.
T3 links AGENTS.md and skills from `~/.gemini` but leaves an empty
`config/mcp_config.json` in the profile, which hid every fleet MCP server from
T3 Antigravity threads. When `t3_antigravity_enabled` is set, the t3 role
replaces a missing or empty profile file with a symlink to the fleet-managed
`~/.gemini/config/mcp_config.json`, so T3 threads get the same stdio servers as
the CLI. A profile file with servers of its own is left alone. T3 0.1.9 and later look on PATH only for their own managed
runtime, so without `binaryPath` the provider reports "not installed" even
when agy is present. T3 0.1.6 rejected agy as binaryPath; every agent host ran
0.1.10 or later when this default was added on 2026-11-20.

The role default `t3_antigravity_enabled: false` leaves provider settings alone.
Opting in fills missing keys in `providerInstances.antigravity`:
driver `antigravity`, enabled `true`, config.authMethod `oauth-personal` and
config.binaryPath `t3_antigravity_binary_path` (the mise `latest` agy).
Existing values, including disabled state and authentication choices, win.
T3 reloads settings without restart; sign-in is manual on each host.

Sign-in from T3 settings works only where agy can open a browser. On a host
without a display it fails with "No browser is available here"; on omarchy-pc
the browser opens on the locked autologin desktop. In both cases run the login
in a terminal on that host with T3's profile directory, open the printed
Google URL elsewhere and paste back the code:

    P=$(ls -d ~/.t3/userdata/providers/antigravity/*/); P=${P%/}
    AGY_ACP_FORCE_FILE_STORAGE=1 GEMINI_HOME=$P BROWSER=true \
      agy acp --gemini-dir "$P" --app-data-dir antigravity-acp --login

T3 reads the token from `$P/antigravity-acp/antigravity-oauth-token`. Where a
Secret Service keyring is reachable, agy 1.5.13 stored the token in the keyring
(service `gemini`, user `antigravity`) instead of that file even with
AGY_ACP_FORCE_FILE_STORAGE set, so check that the file exists afterwards.

The final inventory enablement commit must follow a Chaldea client release
and pin bump that accepts `usageLimits: null`. Client v0.4.27 fails route
catalog reads while this provider is enabled. Do not merge the enablement
ahead of that dependency.

Sources: [Google update troubleshooting](https://antigravity.google/docs/cli/troubleshooting),
[CLI settings](https://antigravity.google/docs/cli-settings),
[Aqua registry](https://github.com/aquaproj/aqua-registry/blob/main/pkgs/google-antigravity/antigravity-cli/registry.yaml),
[1.5.13 assets](https://github.com/google-antigravity/antigravity-cli/releases/tag/1.5.13).
