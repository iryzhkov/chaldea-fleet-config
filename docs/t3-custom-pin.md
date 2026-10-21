# omarchy-pc custom T3 pair

Only `omarchy-pc` overrides the shared official T3 0.1.0 and Chaldea
client-v0.4.11 pins. Its managed pin preserves an already manually activated
pair. Pull never installs, updates, downgrades or restarts this custom T3.

The T3 binary embeds version 0.0.45. It is a custom build from
`161de7bb3e948490fd8af5b0da16c034067a5685`, not the official 0.0.45 release.

| Artifact | SHA-256 |
| --- | --- |
| Exact original custom T3 xz archive | `ad50546a2bce82ae04b8fd57cc75e9df97bdd3965dc5c7a08320904ba4bee403` |
| T3 executable | `18c808e79a4c84ba64e0ef1e064de94838f22789f0dc650e8b5cddff33dae495` |
| Canonical client-v0.4.17 archive | `81a1c1860ff3194a288fa4518bfca3e46dbc732ee23c872aebb6382afbd50839` |
| Canonical client-v0.4.17 manifest | `59e497c9d929d8259145a49566c7601580d733ca1dcc0be99b3a7a856073f4f6` |

[client-v0.4.17](https://github.com/iryzhkov/chaldea/releases/tag/client-v0.4.17)
was published by the existing client artifact workflow,
[run 39609757879](https://github.com/iryzhkov/chaldea/actions/runs/39609757879),
from merged Chaldea `53c53cff4a883876993c4f1cbc82ff2fb0d83dca`.
It contains the accepted `8bdc977c23239068da1634d5520150779e7baecd`
repair. Its archive is byte-identical to the client used in the live canary.
The role uses the ordinary canonical release URL, archive pin, manifest and
immutable-release verification. Production uses no fixture archive inputs.

## Admission and pull order

The optional `t3_required_binary_sha256` guard defaults to empty. Official
hosts retain their existing behavior. When set, the client role imports the
read-only T3 admission tasks before any client write, including configuration,
download, release installation or link changes. This also covers a targeted
`--tags chaldea_client` pull. The later T3 role repeats the same admission.
No site-wide deployment order changes are needed.

Admission requires valid custom source/archive provenance, upgrades disabled,
the exact selected version and binary SHA-256, an active/running loaded service
whose ExecStart selects that version's launcher, matching managed server
metadata, and matching SHA-256 of both live process executables under /proc.
A different official binary with the same 0.0.45 version fails admission.
Missing files, stale service selection, inactive services and mismatched live
processes fail before client changes. The provenance fields document identity;
the trusted executable checksum enforces it. This guard does not attest every
package resource or perform authenticated runtime capability/UI acceptance.

On an already activated pair, run the normal host-limited pull in CHECK, REAL
and SECOND modes, preserving the existing host identity and checksum checks.
SECOND must report changed=0 for the scoped roles, with the exact T3 bytes
and client current link retained. This source change alone does not establish
live convergence or UI acceptance. Unrelated roles remain outside this task.

## Coordinated manual activation and rollback

Root owns activation after authenticated UI acceptance and independent source
review. Merging fleet main can activate pull timers, so keep timer coordination
inside that approved rollout. While the restored official pair is running,
this pin deliberately refuses before switching its client.

Before disruption, record service identities and current/previous client links,
retain the verified prior official runtime and client, and complete protected
SQLite online snapshots plus config/journal backups. Retain newer userdata
and journals through both activation and rollback.

Quiesce waits/quota for the coordinated transition. Stage and verify the
canonical client-v0.4.17 using the existing archive/manifest mechanism. Use
the supported Chaldea `t3 restart --restart-config <reviewed-config>` path
with the existing T3 `service install --base-dir <base> --allow-downgrade`
installer and its supported `T3CODE_RELEASE_BASE_URL` override. Serve the
exact original custom archive and its checksum through the reviewed mirror
path; never silently ask the official release service for 0.0.45.
The qualified installer lookup filename ends in tar.gz while the unchanged
archive bytes are xz; tar compression detection was tested, without repacking
or relaxing any installer verification. Select the matching client atomically,
then start waits/quota after verifying T3 identity and runtime readiness.
Do not use `t3_allow_upgrade=true` or a raw T3 systemctl restart.

After activation, verify package contents and exact executable hash, service
and runtime identity, authenticated UI, actual providers, fresh persisted wake
through automatic settlement, Stop suppression and immutable replay. Reconcile
restart journal outcomes before retrying an interrupted operation. Pull
admission is only the permanent preservation check for this accepted pair.

For rollback, first stop concurrent pulls under the existing rollout authority.
Quiesce waits/quota and use supported Chaldea restart with the retained exact
official 0.1.0 `service install` command. Restore the retained canonical
client-v0.4.11 link atomically and restart its waits/quota. Coordinate restoring
the official inventory pins before resuming pulls; the custom guard must refuse
a mixed or restored official pair. Keep all new data and reconcile journals,
rather than restoring an older database automatically.

Quarantine the inactive custom numeric versions/0.0.45 cache after returning
to official T3. Preserve its package and provenance outside that numeric
cache so a future official 0.0.45 install cannot mistake custom bytes for an
official cache entry. Never overwrite an existing official cached release.

The completed canary and deliberate restoration evidence live at
`/home/igor/.cache/guidance-consistency-20261021/canary-omarchy/install-path-r2/report.txt`
and `checkpoint.json`. Agent-a installer qualification job
`f6f9f062-5ce4-4fe3-b94a-2e5e46a9d611` proved the existing mirror path.
Root retains the later authenticated UI and permanent rollout receipts.
