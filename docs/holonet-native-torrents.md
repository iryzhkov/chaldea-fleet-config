# Native HoloNet torrent reader

Source capability only. `webmcp_interactive_holonet_torrents_enabled` defaults to
false, with no inventory opt-in. Enabling it requires the existing writer
capability on laptop UID 1001 before any staging writes.

The separate `holonet_janitor_torrents` registration supports Claude and Codex
at the fixed URL `https://media.mcp.ryzhkov.dev/mcp`. Its only helper command is
`/usr/local/libexec/webmcp-interactive-headers holonet-torrents laptop`.

The helper reuses the existing writer account, protected app-password path,
token exchange, issuer, JWKS and RS256 verifier. It requests exactly
`holonet.read holonet.janitor holonet.torrents` and accepts only the flat
`managed-janitor` grant for library `3`, empty catalog/history/targets and
actions exactly `["janitor.torrents.read"]`. Extra private HoloNet claims and
mixed grants fail closed. No CLI option selects a resource, action or scope.

The existing `holonet-janitor laptop` mode and `holonet_janitor` registration
retain their original two-action contract. The torrent resource
`homelab-qbit-movies` belongs to root endpoint policy and is never a caller grant.

This change does not enroll an issuer grant, update the installed helper pin,
or activate inventory. Build/release and combined acceptance belong to root
after final source review. No live authentication or torrent read is qualified.
