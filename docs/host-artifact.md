# Pinned Chaldea host installation

Fleet configuration installs `chaldea-host.tar.gz` and `manifest.json` from
`https://github.com/iryzhkov/chaldea/releases/download/VERSION/`.
Inventory pins `chaldea_host_version` (an immutable `host-vX.Y.Z` tag) and
`chaldea_host_sha256`. The shared `chaldea_host_artifact` role checks the archive
against that SHA-256 and requires manifest fields `version` and `sha256` to match.
It extracts root-owned source under `/opt/chaldea-host/releases/VERSION/host`.
A fresh check run explains the missing cache and defers program copies. A cached
check verifies pins; it does not download or extract. Apply requires all ten
payload files. After a successful apply, Ansible retains the configured release
plus the most recently installed prior release and their archive/manifest cache
files. It removes other managed version directories and cache files without
following symlinks; unrelated cache files are preserved. Check mode never prunes.
`chaldea_host_artifact_preserve_versions` additionally keeps at most five unique
exact older releases that already exist; it never installs a missing one.

The job-host, retention, timer-reporting, access-trust and collector roles consume
this role. Configuration, users, authorized keys, services, mount units and firewall
policy retain their roles and destinations. No host has been enrolled by this change.

## Install destination comparison against fleet base 6f4d6eb

| Program | Before | After | Mode | Production ownership |
| --- | --- | --- | --- | --- |
| job server | /usr/local/libexec/chaldea-job-server-v1 | same | 0755 | root:root, preserved |
| toolchains | /usr/local/libexec/chaldea-job-toolchains | same | 0755 | root:root, preserved |
| image helper | Ansible script module's temporary upload | /usr/local/libexec/chaldea-job-image | 0755 | new root:root command |
| trust fetcher | /usr/local/libexec/chaldea-access-trust-fetch | same | 0755 | root:root, preserved |
| retention | ~/.local/bin/chaldea-retention | same | 0755 | operator-owned becomes root:root |
| timer reporter | ~/.local/bin/chaldea-timer-report | same | 0755 | operator-owned becomes root:root |
| callback | ~/.local/share/chaldea/timer-reporting/chaldea_outcome.py | same | 0644 | operator-owned becomes root:root |
| protocol data | embedded server constants | /usr/local/libexec/exec-protocol.json | 0644 | new root:root file |
| trust maintenance | /opt/chaldea/app/src/access/maintenance.ts, separately staged | /opt/chaldea-host/releases/VERSION/host/access-maintenance.mjs | 0644 | root:root |
| collector | ~/.local/share/agent-tools/current/chaldea/src/events/collector.ts | /opt/chaldea-host/releases/VERSION/host/akasha-collector.mjs | release payload | root:root |

The default job server and fetcher destinations remain configurable as before.
The protocol JSON is installed first and follows the configured server's directory.
Extraction preserves archived permissions regardless of the invoking user's umask;
the extracted host directory is explicitly secured to 0755.
The image call now invokes `python3 -I /usr/local/libexec/chaldea-job-image` as root.
The callback stays at its existing path and the reporter needs no wrapper.

The retention unit adds `Environment=CHALDEA_NODE_VERSION=VERSION`; its arguments,
priority and timer remain unchanged. The reporter consolidates feed and queue modes:
`~/.config/chaldea/timer-reporting.json` contains `{"delivery":"feed"}` by default
and `{"delivery":"queue"}` when the collector is enabled. The existing failure-handler
unit remains unchanged. The collector uses `chaldea_node_version` rather than a
second literal version. Its timer stays disabled by default.

`chaldea_access_paths` in inventory is the canonical filesystem map. Role defaults,
updater output/health configuration, bootstrap-state check and the clock unit derive
from it. The current bundle, clock-health and updater paths keep their existing
values. The verifier path is `/var/lib/akasha/access-state.db`, separately owned from
the root-only 0700 updater state directory. Fleet does not alter that service's owner.

## Evidence and limits

Huyang reads compared these original programs from detached fleet base `6f4d6eb`
against their current `chaldea-host/host` counterparts. Their text bytes match
exactly: image helper 2,182 bytes; toolchains 14,993; fetcher 5,019; callback 3,732.
Reporter consolidation, retention de-templating and server protocol sharing are
intentional program changes; no equality claim applies to those programs.

`tests/test_host_artifact.py` installs a checksummed release through the real artifact
role. It rejects archive and manifest mismatches, checks a fresh uncached dry run,
and checks idempotence. It also executes the production eight program-copy tasks
with destinations redirected into scratch and privilege/ownership set to the test
UID. It compares each installed file with the extracted artifact and verifies its
mode. A clean `--check --diff` changes nothing; deliberate installed-server drift
produces exactly one predicted change and leaves the drifted file untouched.

These checks exercise program installation, not real-host users, mounts, firewalls,
system units, trust bootstrap, or root privilege escalation. Synthetic fixtures
contain distinct inert payload bytes. They do not establish runtime acceptance or
equality with a release that has not yet been built.

To exercise the same harness with the candidate release, provide both
`CHALDEA_HOST_TEST_ARCHIVE` and `CHALDEA_HOST_TEST_MANIFEST`, naming files included
in the Chaldea job snapshot, and run `bash tools/ci.sh` through `chaldea exec`.
The fixture verifies the manifest SHA-256, uses its version, and copies those exact
archive bytes. All test HOME/TMPDIR values must remain isolated disk scratch.

## Final candidate verification, 2026-10-17

Chaldea job `585d9b56-7732-4d5c-8174-ce8040a746b5` on agent-a exited 0.
It ran `bash tools/ci.sh` against fleet Huyang source revision `wsrev_123`,
with the real `host-v0.1.0` archive SHA-256
`f83769273ffe568c5748a0eccccf5a812d4f31c25be9e62ce00a9423ddc1d71e`.
The SSH fixture comparison used exact public Chaldea commit
`e021bdfe9f7cc5b2e5d50e587e38fc81e6250466`.

Results: 77 Python tests passed and four namespace tests skipped. Production
ansible-lint passed 105 files with no failures or warnings. Syntax and synthetic
check-mode runs passed; first apply changed 27 tasks and second apply changed zero.
User-timer, data-disk and job-client fixtures finished with zero unrescued failures;
their rejection cases were deliberately rescued by the fixture plays.

The real candidate contained exactly the ten runtime files. All were owned by uid/gid
0 in the isolated job namespace. Executable Python programs were 0755; callback,
protocol JSON and both bundled .mjs files were 0644. All eight production copy-task
destinations matched the extracted candidate bytes and configured modes.
The clean copy harness dry run reported `ok=19 changed=0 failed=0`; after deliberate
server drift it reported `ok=19 changed=1 failed=0`, leaving the drifted bytes intact.
Ansible's remote-source copy task reports the predicted change without a textual
content diff.

The local evidence is under
`.chaldea/artifacts/585d9b56-7732-4d5c-8174-ce8040a746b5/`:
`.scratch/fleet/ci.log`, `.scratch/fleet/role-install-evidence/files.json`,
`clean-check.log` and `drift-check.log` in that evidence directory, and
`.ci-home/second-run.log`. Evidence and the temporary candidate inputs are not
committed; the inputs were removed after verification.

The fleet test suite retains official toolchain archive/checksum schema coverage.
It compares Chaldea's source-owned frozen SSH daemon and authorized-key fixtures with
the deployed fleet templates. CI uses the immutable host release tag by default;
`CHALDEA_HOST_TEST_SOURCE_REF` selects an exact public candidate commit before the
tag is published.
