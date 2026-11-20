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
a changed file is serialized as plain JSON. Remote registrations and managed
HTTP authentication remain limited to their existing providers. A scratch
1.5.13 probe confirmed that stdio children inherit DBUS_SESSION_BUS_ADDRESS,
XDG_RUNTIME_DIR and HUYANG_SOCKET from the CLI's environment, so no values
from the converging Ansible process are captured in configuration.

T3 uses its own managed Antigravity ACP runtime and a private per-instance
GEMINI_HOME. The CLI guidance and MCP configuration above do not configure T3
sessions; T3 links skills only. Do not set binaryPath to the agy executable.

The role default `t3_antigravity_enabled: false` leaves provider settings alone.
Opting in fills missing keys in `providerInstances.antigravity`:
driver `antigravity`, enabled `true`, config.authMethod `oauth-personal`.
Existing values, including disabled state and authentication choices, win.
T3 reloads settings without restart; sign-in is manual on each host.

The final inventory enablement commit must follow a Chaldea client release
and pin bump that accepts `usageLimits: null`. Client v0.4.27 fails route
catalog reads while this provider is enabled. Do not merge the enablement
ahead of that dependency.

Sources: [Google update troubleshooting](https://antigravity.google/docs/cli/troubleshooting),
[CLI settings](https://antigravity.google/docs/cli-settings),
[Aqua registry](https://github.com/aquaproj/aqua-registry/blob/main/pkgs/google-antigravity/antigravity-cli/registry.yaml),
[1.5.13 assets](https://github.com/google-antigravity/antigravity-cli/releases/tag/1.5.13).
