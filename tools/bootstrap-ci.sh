#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PIP_CACHE_DIR="$ROOT/.cache-ci/pip" TMPDIR="$ROOT/.cache-ci/tmp"
mkdir -p "$TMPDIR"
PYTHON=${CI_PYTHON:-python3.13}
"$PYTHON" -c 'import sys; assert sys.version_info[:3] == (3, 13, 5), sys.version'
LOCK=$("$PYTHON" -c 'import hashlib; print(hashlib.sha256(open("requirements-ci.txt","rb").read()).hexdigest())')
if [[ ! -d .venv-ci ]]; then
  "$PYTHON" -m venv .venv-ci
fi
if [[ ! -f .venv-ci/lock.sha256 ]] || [[ $(< .venv-ci/lock.sha256) != "$LOCK" ]]; then
  .venv-ci/bin/python -m pip --isolated install --cache-dir "$PIP_CACHE_DIR" --disable-pip-version-check --require-hashes --only-binary=:all: -r requirements-ci.txt
  printf '%s\n' "$LOCK" > .venv-ci/lock.sha256
fi
.venv-ci/bin/python - <<'PY'
import importlib.metadata as m
import pathlib
import sys
assert sys.version_info[:3] == (3, 13, 5), sys.version
for line in pathlib.Path("requirements-ci.txt").read_text().splitlines():
    if line and not line.startswith("#"):
        name, version = line.split(" --hash=")[0].split("==")
        assert m.version(name) == version, (name, m.version(name), version)
print("Verified Python", sys.version.split()[0], "and all locked distributions")
PY
for tool in python3 ansible-playbook ansible-lint; do
  test -x ".venv-ci/bin/$tool" || { echo "Missing local executable: $tool" >&2; exit 1; }
done
