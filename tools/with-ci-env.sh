#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
bash tools/bootstrap-ci.sh
export PATH="$ROOT/.venv-ci/bin:$PATH"
export TMPDIR="$ROOT/.cache-ci/tmp" XDG_CACHE_HOME="$ROOT/.cache-ci"
export ANSIBLE_LOCAL_TEMP="$ROOT/.cache-ci/ansible" ANSIBLE_FORKS=3
export GOMAXPROCS=3 GOFLAGS=-p=3 MAKEFLAGS=-j3 CARGO_BUILD_JOBS=3
exec "$@"
