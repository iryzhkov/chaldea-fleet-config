# Native HoloNet library management

Default-off source for contract `jocasta:d07e09665f67d1ea7b2fb00eae9b6fe0@1`.
No inventory enables this mode yet. Deployment, issuer enrollment and native
acceptance remain separate from source support.

Two closed commands authenticate as the M3 host accounts enrolled through
`homelab-infra`'s `authentik-agent-hosts` path (`chaldea-laptop` and
`chaldea-omarchy-pc`), reuse the fixed HoloNet issuer/JWKS verifier and request
only scope `holonet.library`:
`webmcp-interactive-headers holonet-library laptop` and
`webmcp-interactive-headers holonet-library omarchy-pc`.
No caller may supply scopes, actions, resources, URLs, libraries or another host.

The signed token must carry exact scope `holonet.library`, audience
`https://media.mcp.ryzhkov.dev/mcp`, server `3c86e6d7ff6c4a3296522cdf03d22bb0`,
namespace `managed-library`, libraries `["3", "615", "1132"]`, actions
`["library.read", "library.manage"]`, and empty `holonet_catalog_users`,
`holonet_history_users` and `holonet_target_users`.
Mixed-scope, extra, duplicate, expired, nested or foreign claims refuse.

On both hosts, the helper requires the root-owned host identity selector
(`/etc/webmcp-interactive/host-identity-<host>`) and reads the owner's protected
`~/.config/chaldea/authentik/host.app-password` (`0600`, single-link regular
file under `0700` `~/.config/chaldea/authentik`, no symlinks). It never uses the
original writer username (`chaldea-laptop-holonet-recommendations`) or
`holonet-recommendations.app-password`, and never falls back when the host
identity selector or `host.app-password` is missing or unsafe:
- `laptop` (node `omarchy-macbook-air-igor`, UID `1001`): `chaldea-laptop` via
  `host.app-password`.
- `omarchy-pc` (node `omarchy-pc`, UID `1000`): `chaldea-omarchy-pc` via
  `host.app-password`.

The flag `webmcp_interactive_holonet_library_enabled` defaults `false`.
Selection requires a strict boolean, bound host/UID (`laptop` UID `1001` or
`omarchy-pc` UID `1000`), and `chaldea_host_identity_enabled: true`, so
`roles/webmcp_interactive/tasks/host-identity.yml` verifies private custody of
`host.app-password` without reading it and installs the host identity selector.
Separate Claude and Codex registrations use name `holonet_library`, URL
`https://media.mcp.ryzhkov.dev/mcp` and the installed helper command. OpenCode,
Antigravity and other hosts are excluded.
