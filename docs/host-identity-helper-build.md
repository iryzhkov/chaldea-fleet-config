# Selector-aware helper build receipt

Preparation only; no helper was installed and no host switch was enabled.

Source: PR172 base d715028c6383e3ba3a08d0dbc64e08ef4406e472.
Production helper source is unchanged in this fix round. Tests add selector fixtures.
Chaldea job ade8955f-22bf-4f6a-8671-0f6f312ebd5a on agent-a, exit 0,
Go go1.27.0 linux/amd64. Full Go tests passed; ARM64 was cross-built,
not executed. The flags/toolchain match the current personal-client helper
build documented in docs/ov-personal-client-activation.md.

Run from this checkout (Chaldea selects the job host):

```sh
chaldea exec --artifact helper-amd64 --artifact helper-arm64 -- bash -c '
set -euo pipefail
cd /work
test "$HOME" = /home/job
export TMPDIR=/home/job/ci
mkdir -p "$TMPDIR"
cd tools/webmcp-interactive-headers
go version
HUYANG_FRICTION=0 go test -count=1 ./...
for arch in amd64 arm64; do
  CGO_ENABLED=0 GOOS=linux GOARCH=$arch go build -trimpath -ldflags="-buildid=" -o /work/helper-$arch .
done
sha256sum /work/helper-*
'
```

| Inventory architecture | Artifact | SHA256 |
| --- | --- | --- |
| x86_64 | helper-amd64 | 8f091dc9579db25e2f58b62963e9330814da0ad28b9079dd7129603d20a333fc |
| aarch64 | helper-arm64 | 4417f939c2a23f7d6e87d68373985a3065cce0434093f26c80422469a604a66f |

Returned artifacts are under .chaldea/artifacts/ade8955f-22bf-4f6a-8671-0f6f312ebd5a/.
The separate webmcp_interactive_host_identity_helper_checksums map is a
capability allowlist, not a replacement for any existing default or host pin.

## Per-host cutover prerequisite

Before flipping chaldea_host_identity_enabled, coordinate pull writers and
install the architecture's selector-aware binary at
/usr/local/libexec/webmcp-interactive-headers with root:root 0755 custody.
Retain the previous reviewed artifact for rollback. Update that host's
webmcp_interactive_helper_source, webmcp_interactive_helper_sha256 and previous
pin through the normal guarded upgrade procedure. Verify the installed SHA256
against the capability map. Then follow docs/host-identity-cutover.md,
including credential delivery, CHECK review and native acceptance.
The role refuses selection unless both the already installed binary and the
controller copy source match this architecture's selector-aware pin. A legacy,
missing or wrong-architecture installed helper cannot select host identity.
Switch-off hosts retain all existing pins and helper bytes.

## Read-only host binding observations

Observed 2026-11-12 over SSH: agent-a / 1000; agent-b / 1000;
omarchy-pc / 1000; laptop nodename omarchy-macbook-air-igor / 1001.
UIDs are for igor. No table correction was needed.
The PC's direct self-SSH was refused; its observation used the laptop's existing
gaming-pc SSH alias. No host configuration or credential was changed.

Selector fixtures include absence, exact content, malformed content, symlinks
(including dangling), and wrong ownership. Chaldea's single-UID job namespace
cannot chown to UID 1000, so that subcase is explicitly skipped there;
the non-root fixture exercises wrong ownership in hosted CI.
