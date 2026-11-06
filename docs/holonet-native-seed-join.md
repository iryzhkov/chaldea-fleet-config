# Native HoloNet stat-only seed join

Source successor to `jocasta:c3070dfe196e7f67732749db4b279689@3`.
The separate `holonet_janitor_seed_join` registration supports Claude and Codex
at the fixed URL `https://media.mcp.ryzhkov.dev/mcp`. Its only command is
`/usr/local/libexec/webmcp-interactive-headers holonet-seed-join laptop`.
OpenCode, other hosts, caller flags, paths, actions and scopes are refused.

`webmcp_interactive_holonet_seed_join_enabled` defaults to false. The role
requires a boolean flag, laptop UID 1001 and the existing writer capability before
staging. No inventory opts in. The client does not depend on the torrent opt-in:
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

## Activation successors owned by the parent

This change is source only. It does not enroll the new signed scope or change
helper artifacts, SHA pins, inventory, credentials or hosts. Parent integration
must complete exact-head producer/consumer/native-client review, obtain a reviewed
compatible helper artifact and update its pin separately. Actual enrollment of
`holonet.seedjoin` / `janitor.seed_join.read` needs Igor's separate new-access
decision. Only after that decision may the parent select the registration and
flag, converge the approved laptop and verify native acceptance. Filesystem
stat-only approval does not approve signed-scope enrollment.
