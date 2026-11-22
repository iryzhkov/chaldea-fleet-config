# Native HoloNet library management

Default-off source for contract `jocasta:d07e09665f67d1ea7b2fb00eae9b6fe0@1`.
No inventory enables this mode yet. Deployment, issuer enrollment and native
acceptance remain separate from source support.

Two closed commands authenticate as the existing original HoloNet writer
account (`chaldea-laptop-holonet-recommendations`), reuse the fixed HoloNet
issuer/JWKS verifier and request only scope `holonet.library`:
`webmcp-interactive-headers holonet-library laptop` and
`webmcp-interactive-headers holonet-library omarchy-pc`.
No caller may supply scopes, actions, resources, URLs, libraries or another host.

The signed token must carry exact scope `holonet.library`, audience
`https://media.mcp.ryzhkov.dev/mcp`, namespace `managed-library`, libraries
`["3", "615", "1132"]`, actions `["library.read", "library.manage"]`, and empty
`holonet_catalog_users`, `holonet_history_users` and `holonet_target_users`.
Mixed-scope, extra, duplicate, expired, nested or foreign claims refuse.

On both hosts, the helper reads the owner's protected
`~/.config/chaldea/authentik/holonet-recommendations.app-password` (`0600`,
single-link regular file under `0700` `~/.config/chaldea/authentik`, no
symlinks) and never falls back to `host.app-password` or another credential,
even when `chaldea_host_identity_enabled` is active:
- `laptop` (node `omarchy-macbook-air-igor`, UID `1001`): reuses the existing
  original writer credential.
- `omarchy-pc` (node `omarchy-pc`, UID `1000`): uses the separate
  `extra_tokens` app password (`chaldea-laptop-holonet-recommendations-omarchy-pc-g<N>`)
  delivered by `homelab-infra`'s `authentik_machine_identities` role to
  `/home/igor/.config/chaldea/authentik/holonet-recommendations.app-password`
  owned by `igor` (`0600`).

The flag `webmcp_interactive_holonet_library_enabled` defaults `false`.
Selection requires a strict boolean and bound host/UID (`laptop` UID `1001` or
`omarchy-pc` UID `1000`), and verifies private custody of
`holonet-recommendations.app-password` without reading it. Separate Claude and
Codex registrations use name `holonet_library`, URL
`https://media.mcp.ryzhkov.dev/mcp` and the installed helper command. OpenCode,
Antigravity and other hosts are excluded.
