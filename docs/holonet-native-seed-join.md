# Native HoloNet stat-only seed join

Source successor to `jocasta:c3070dfe196e7f67732749db4b279689@3`.
The separate `holonet_janitor_seed_join` registration supports Claude and Codex
at the fixed URL `https://media.mcp.ryzhkov.dev/mcp`. Its only command is
`/usr/local/libexec/webmcp-interactive-headers holonet-seed-join laptop`.
OpenCode, other hosts, caller flags, paths, actions and scopes are refused.

`webmcp_interactive_holonet_seed_join_enabled` defaults to false. The role
requires a boolean flag, laptop UID 1001 and the existing writer capability before
staging. Only laptop inventory opts in; other hosts and helper modes remain
unchanged. The client does not depend on the torrent opt-in:
its dedicated authentication contract is independent. The issuer's torrent
dependency preserves backend source bindings and remains the issuer's concern.

The helper reuses the writer account, protected credential, exchange, issuer and
JWKS verifier. It requests and verifies exactly the scope set
`holonet.read holonet.janitor holonet.seedjoin`, with flat `managed-janitor`
claims: only Movies library `3`, empty catalog/history/target users, and solely
`janitor.seed_join.read`. Duplicate, missing or extra authority is refused.
Unknown private claims, including nested `holonet_seed_join`, are refused.
This mode grants no authority to the torrent, Janitor, reader or writer modes.

Synthetic signed claims, intercepted exchange, registration round trips, role
selection/guards and invalid CLI tuples exercise the boundary without real JWTs
or authentication calls. The stat-only backend contract compares an instantaneous
same-host relation; it does not promise atomicity or future seeding.

## Laptop activation

Igor approved the isolated `holonet.seedjoin` / `janitor.seed_join.read` grant,
reviewed endpoint/helper deployment and one native canary in
`jocasta:c61d194504ef8dd2318e1a1e3e1a5bfc@3`. Fleet source merged at
`8512a21e2095569f9ce23e5b169466743815a527`.

Laptop inventory persists the already installed static Linux/ARM64 helper SHA256
`9086fa224b660314c3aff7d09ec5a8f4a5e344011151eb125c84c6b2efe236b3`, from runtime
source `c04c798d00de13ed52e9fbbdbd49e3d0e81668cc` and Chaldea build
`3b4ed168-d126-4bd7-8613-664bd7cf8a96`. One guarded REAL and an identical
unchanged repeat are recorded at `jocasta:1bafe232420100bbca3f8a118a30878b@1`.
The previous SHA256
`59336572c6350fc7779844083c5d5d4bded5536b08c95f5a99ae9bf3446849a2` is the
public rollback input.

Exactly one native GOAT canary returned `linked` with
`media_removal_authorized: false` at 2026-11-07T20:28:27.949Z, recorded at
`jocasta:b5c3380ab7e3ffdd8002e1d5615b1677@1`. This qualifies the native tool for
that one pair at that instant only. It does not establish continued seeding,
durable identity, an atomic snapshot, freed space, playback completeness,
eligibility or removal authority. Removal remains blocked. Do not repeat the
canary for this persistence change. Publication and convergence belong to root;
this follow-through adds no grant, scope, account or helper code change.
