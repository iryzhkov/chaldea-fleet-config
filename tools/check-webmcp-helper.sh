#!/usr/bin/env bash
# Standalone helper source/fixture gate. Native T3 acceptance remains separate.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
helper_check_home="${HOME:?}/.cache/managed-helper-check/home"
export HOME="$helper_check_home"
test "$HOME" = "$helper_check_home"
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"
cd tools/webmcp-interactive-headers
HUYANG_FRICTION=0 go test -count=1 ./...
go build -trimpath -o "$HOME/webmcp-interactive-headers" .
# Open or unknown tuples fail generically before any file or network access.
# The real "ov laptop", "ov-full HOST" and "jocasta HOST" modes are never invoked here.
for args in "invalid" "ov" "ov agent-a" "ov laptop extra" "ov --url=https://other.invalid/mcp" "jocasta homelab" \
    "ov-full" "ov-full agent-a" "ov-full controller" "ov-full laptop extra" "ov-full --host=laptop" "ov omarchy-pc" \
    "holonet-writer" "holonet-writer agent-a" "holonet-writer laptop extra" "holonet-writer --policy=other" \
    "holonet-janitor" "holonet-janitor agent-a" "holonet-janitor laptop extra" "holonet-janitor --scope=holonet.home" \
    "holonet-torrents" "holonet-torrents agent-a" "holonet-torrents laptop extra" \
    "holonet-torrents --scope=holonet.read" "holonet-torrents laptop --action=janitor.torrents.read" \
    "holonet-seed-join" "holonet-seed-join agent-a" "holonet-seed-join omarchy-pc" \
    "holonet-seed-join laptop extra" "holonet-seed-join laptop --scope=holonet.seedjoin" \
    "holonet-seed-join laptop --action=janitor.seed_join.read" "holonet-seed-join laptop --path=/movies" \
    "holonet-seed-join laptop --url=https://other.invalid/mcp"; do
    # shellcheck disable=SC2086
    if "$HOME/webmcp-interactive-headers" $args 2>"$HOME/error" >"$HOME/output"; then
        echo "helper admitted invalid arguments: $args" >&2
        exit 1
    fi
    test "$(cat "$HOME/error")" = "managed headers unavailable"
    test ! -s "$HOME/output"
done
