#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
bash tools/bootstrap-ci.sh
export PATH="$ROOT/.venv-ci/bin:$PATH"
export TMPDIR="$ROOT/.cache-ci/tmp" XDG_CACHE_HOME="$ROOT/.cache-ci"
export ANSIBLE_LOCAL_TEMP="$ROOT/.cache-ci/ansible" ANSIBLE_FORKS="${ANSIBLE_FORKS:-1}"
export GOMAXPROCS="${GOMAXPROCS:-1}" GOFLAGS="${GOFLAGS:--p=1}"
export MAKEFLAGS="${MAKEFLAGS:--j1}" CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
exec "$@"
