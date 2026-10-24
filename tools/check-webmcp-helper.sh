#!/usr/bin/env bash
# Standalone helper source/fixture gate. Native T3 acceptance remains separate.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
export HOME="$PWD/.cache/managed-helper-check/home"
test "$HOME" = "$PWD/.cache/managed-helper-check/home"
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"
cd tools/webmcp-interactive-headers
HUYANG_FRICTION=0 go test -count=1 ./...
go build -trimpath -o "$HOME/webmcp-interactive-headers" .
if "$HOME/webmcp-interactive-headers" invalid 2>"$HOME/error"; then
    echo "helper admitted invalid arguments" >&2
    exit 1
fi
test "$(cat "$HOME/error")" = "managed headers unavailable"
