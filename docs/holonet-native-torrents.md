# Native HoloNet torrent reader

`webmcp_interactive_holonet_torrents_enabled` defaults to false. Only laptop
inventory opts in, with the existing writer capability on UID 1001 required
before any staging writes. Other hosts and helper modes remain unchanged.

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

Laptop inventory persists the already installed Linux/ARM64 helper SHA256
`59336572c6350fc7779844083c5d5d4bded5536b08c95f5a99ae9bf3446849a2`, from reviewed
source `d2433ba1f8e474c1ae3b8fba54612f4c72366d8a`, merged equivalent
`150a341145f6a4b3106f2d262948e3ac83365f19`. Chaldea build
`6f5896fb-9254-4db5-9cf0-4ce5ad59eaf9` and guarded CHECK/REAL/repeat are
recorded at `jocasta:2ddd958c8b9a3198406794c487d8f37b@1`. The seed join superset
pin in `holonet-native-seed-join.md` later replaced it with the torrent mode kept.

Exactly one native GOAT canary succeeded at 2026-11-06T11:14:03.787652764Z,
recorded at `jocasta:d25b3ce108c2481234598ec3a9ae71a4@1`. It reported one
complete file and accepted the producer's owned logout contract. Application
paths and seed topology remain unqualified; media removal is unauthorized.
Do not repeat the canary for this persistence change. Publication and convergence
belong to root; this source follow-through adds no grant or helper code change.
