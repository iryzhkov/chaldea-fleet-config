# Ordinary HoloNet catalog reader

This candidate adds ordinary laptop Codex questions about the Movies catalog.
It is separate from the admitted Chaldea preset `holonet-movies-catalog-claude`.
That preset, its credentials and six-call qualification remain unchanged.

The managed tuple is exactly `holonet_catalog`, remote URL
`https://media.mcp.ryzhkov.dev/mcp`, `auth_mode: managed_helper`,
`helper_host: laptop`, and provider `codex`. The registration writes the native
`http_headers_helper` setting. Claude and OpenCode are not selected by this
first release. Extra headers, helpers, scopes, hosts and URLs refuse.

The helper command is
`/usr/local/libexec/webmcp-interactive-headers holonet laptop`. It checks the
actual host and UID, derives home from the account database, and reads only
`~/.config/chaldea/authentik/holonet-interactive.app-password` through the
existing private-file guards. It never reads the limited preset's password.
The fixed ordinary account is `chaldea-laptop-holonet-interactive`.

Each invocation exchanges that password at the fixed Authentik endpoint,
verifies the RS256 signature and exact issuer, client, audience, scope, lifetime
and Movies-only catalog grant, and returns only the native authorization-header
object. There is no persisted JWT, token selector, endpoint override or arbitrary
credential path. The helper has an eight-second total deadline. Neither the
password nor JWT belongs in chat, tool arguments or logs.

`webmcp_interactive_holonet_enabled` defaults to false. It requires the existing
`webmcp_interactive_enabled`, laptop UID1001, private separately delivered
credential metadata and a reviewed helper artifact pin before activation.
Only laptop inventory selects it. Keep the activation candidate unmerged until
guarded staging, exact artifact/native/lifetime acceptance and rollback readiness
pass. Merging activates it through normal pulls. Existing Jocasta and OV helper
modes and registrations remain available. Removing only this named native entry
is the registration inverse; do not withdraw unrelated servers or the preset.

The service candidate supports title search, exact director/composer credit
filters and bounded optional year, genre and credit projection. These remain
under the same fixed user/library/catalog.read ACL. History, UserData and writes
are excluded from this mode.

Source tests are not deployment or native acceptance. Before enabling ordinary
access, qualify the live Emby fields and filters, the exact packaged service,
the new identity and private custody, native allowed/refused calls, and a
same-backend native call after the 300-second JWT lifetime plus 30-second tail.
Record ordinary helper renewal separately from admission-bound native renewal,
which the existing short preset did not exercise. Preserve the working preset
and all other helper modes during guarded rollout and rollback.
