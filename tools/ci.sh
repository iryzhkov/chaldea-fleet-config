#!/usr/bin/env bash
# Every CI gate, runnable locally: build the hashed toolchain from
# requirements-ci.txt, then run the unit tests, ansible-lint, a syntax check and
# a check-mode run against a synthetic inventory whose home is a scratch dir.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

python=${CI_PYTHON:-python3}
venv=.venv-ci
if ! cmp -s requirements-ci.txt "$venv/requirements-ci.txt"; then
	rm -rf "$venv"
	"$python" -m venv "$venv"
	"$venv/bin/pip" install --quiet --require-hashes --no-deps --only-binary=:all: -r requirements-ci.txt
	cp requirements-ci.txt "$venv/requirements-ci.txt"
fi
export PATH="$PWD/$venv/bin:$PATH"

python -m pytest -q -p no:cacheprovider tests
ansible-lint
synthetic=(-i inventory -i tests/synthetic-inventory.yml --limit synthetic)
ansible-playbook "${synthetic[@]}" site.yml --syntax-check
rm -rf .ci-home && mkdir -p .ci-home/data
ansible-playbook "${synthetic[@]}" site.yml --check --diff
