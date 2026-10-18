# FATE role targets

Shared model guidance allows Haiku 5.5 or Luna 6 for bulk reading, or whatever
`chaldea route` recommends. Sonnet is excluded. The maintained source remains
`roles/agent_config/files/claude/omarchy-setup/CLAUDE.md`; the agent-tooling
ownership PR #45 does not move it. Agent and Codex summaries carry the same line.

After pinning a client release with role targets, inventory can opt in through
`chaldea_client_route_targets`. Empty by default, it leaves older clients'
route.json unchanged. Keys in this dictionary override the template's base
route values; use only documented client fields.

```yaml
chaldea_client_route_targets:
  bans: ["*sonnet*"]
  pins:
    bulk-read:
      model: gpt-6-luna
      providerInstanceId: codex
  floors: {builder: 50, critical-review: 49, bulk-read: 30, general: 48}
  minimumTurns: 100
  failureMargin: 0.10
  probationMs: 604800000
  probationShare: 0.10
  scoreMaxAgeMs: 259200000
  announceHost: omarchy-pc
  scores:
    enabled: true
    url: https://AKASHA-HOST
    tokenHelper: /usr/local/bin/chaldea-token-helper
    host: "{{ inventory_hostname }}"
```

Pins override model policy but still require an available catalog model and
allowed effort, review separation and quota admission. Never place an AA key
in this dictionary, inventory, a prompt or the repository. The root-owned 0600
file `/etc/chaldea-route/artificial-analysis-key` exists only on homelab and
Igor supplies it.

Activation requires a compatible Akasha server, source registrations and
source-bound helper grants. The homelab source publishes daily non-secret
scores. Routers have narrowly scoped snapshot reads. One announcement host
publishes pick changes with a persistent outbox. Chaldea's
[route documentation](https://github.com/iryzhkov/chaldea/blob/main/docs/route.md)
contains calibration sources, units, the exact interactive key-placement
command and activation checks.

This source change neither upgrades a client nor enables snapshot collection.
No host convergence is implied.
