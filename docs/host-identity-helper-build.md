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

## Laptop acquisition-identity rebuild (2026-11-14)

Fleet main ae1213374b678866fe0f634d0fe6ae8f02f61945 (PR191) keeps the three
HoloNet acquisition modes on the original writer account and credential while
every other mode follows the selector. Chaldea job
1660b886-fbc6-4150-883b-9919a9ba044a used the recipe above for arm64 only:
helper-arm64 SHA256 268a48219a44c46d35740764cf4067bb2a3e95d86917960b988dc8f17124f038.
The same recipe at e2bef1a reproduced 4417f939 byte for byte. Only the laptop
runs aarch64 with host identity; the x86_64 pin is unchanged because the
acquisition modes are laptop-only.

## HoloNet library helper rebuild (2026-11-22)

Fleet main ac4819f9a3604de96345692e9a2e91656f89a636 (PR203) adds the closed
`holonet-library` mode for laptop and omarchy-pc on their host identities. Chaldea
job 2753e515-a53e-47fb-b111-771a7f2c81e3 used the recipe above:
helper-amd64 68f63634920a5629d26d6480a5aa5c4b60de724746a6d4828e5053a0c5d7f5fa and
helper-arm64 1e8ff2e22d75ee0796c5eca8c6d7e517d433b01bd8328e5e3a64955491a3035a.
The same recipe at ae12133 reproduced 268a4821 byte for byte (job
189237d2-e452-4c72-bd8a-96f7fd30b373). Only laptop and omarchy-pc move; their
capability pins are host-scoped overrides, so agent-a and agent-b keep the shared
x86_64 pin 8f091dc9. Each host's binary is installed root:root 0755 by hand with
the previous binary retained as
`/usr/local/libexec/webmcp-interactive-headers.previous-<first 12 hex>`, then
converged with `--tags mcp_registrations`.

## Shizune budget write scope rebuild (2026-11-22)

Fleet main 7b6358515ebbeec4102fafe6dcbe07a5747cb4c1 (PR208) makes the `shizune`
mode request `shizune.use shizune.budget.write`. Chaldea job
ea4a63aa-439e-49c7-a922-388ba6b29c73 used the recipe above:
helper-amd64 a054538042a7396d746288ebdd42d4262e4cd68908a4d3e0114a1bb8b122e269 and
helper-arm64 736c06be435f748f4265728daf08789b6d4809c9d6fc221fe1d3583d17d31d5f.
Only laptop and omarchy-pc move, through their host-scoped pins; each previous
binary is retained as `webmcp-interactive-headers.previous-<first 12 hex>`.

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
