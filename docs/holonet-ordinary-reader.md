# Ordinary HoloNet catalog reader

The laptop Codex reader is released. This extension also selects ordinary
laptop Claude through the same maintained Ansible role used for Jocasta.
Claude installation and actual native qualification are reported separately
from source support. The admitted Chaldea preset
`holonet-movies-catalog-claude`, its identity and fixed prompt remain separate.

The closed tuple is `holonet_catalog`, URL
`https://media.mcp.ryzhkov.dev/mcp`, `auth_mode: managed_helper`,
`helper_host: laptop`, with approved providers `claude` and `codex`.
Claude receives native `type: http` and `headersHelper`; Codex receives
`http_headers_helper`. Both invoke exactly
`/usr/local/libexec/webmcp-interactive-headers holonet laptop`.
OpenCode and other hosts remain excluded. Extra headers, helpers, scopes,
hosts and URLs refuse.

The unchanged public helper verifies actual host/UID, derives home from the
account database and reads only the private single-link ordinary
`~/.config/chaldea/authentik/holonet-interactive.app-password`.
The fixed identity is `chaldea-laptop-holonet-interactive`; it is not the
limited preset credential. Each invocation privately obtains and verifies
a bounded RS256 token for the exact issuer/client/resource/scope/Movies
catalog grant. No new password, account, token store or authentication
mechanism is needed for the second ordinary native client. Neither password
nor JWT belongs in chat, tool arguments or logs.

`webmcp_interactive_holonet_enabled` defaults off and additionally requires
the existing managed-interactive opt-in, laptop UID1001, protected credential
metadata and the accepted public helper pin. Only laptop inventory selects it.
The provider list defaults to both approved clients. An explicit
`mcp_registrations_remote_servers` entry named `holonet_catalog` can select
an approved provider subset and state. For a Claude-only inverse, preserve the
original remote-server declarations and add that entry with
`providers: [claude]`, `state: absent`. The role then removes only the
Claude HoloNet entry and leaves installed Codex HoloNet and other servers
unchanged. OpenCode in that list refuses before native registration.
Disabling an opt-in alone does not remove an existing native entry.

Use the canonical pinned laptop `site.yml --tags mcp_registrations`,
review the complete CHECK before REAL and require repeat changed0. Main
merges activate ordinary pulls, so serialize guarded staging/merge/rollout
inside a fresh safe timer gap. Verify each newly selected native client with
actual allowed/denied catalog calls before retaining its entry. On failure
perform the exact own-client inverse and reconcile the owning source.

The service supports bounded title search and Director/Composer credit filters
under fixed Movies/catalog.read ACLs. History, UserData, writes and mutation
tools are excluded. Composer-positive coverage remains dependent on real
credits. Igor adopted the initial reader release with long-session renewal,
identical backend/MCP connection continuity, failed renewal and revocation
explicitly unqualified. Initial read proof does not establish those lifecycle
properties. Keep them as separate follow-ups; do not inspect headers, invent
dummy turns or label synthetic helper checks as native renewal.
