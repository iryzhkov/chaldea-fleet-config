#!/usr/bin/env bash
# Every CI gate, runnable locally: build the hashed toolchain from
# requirements-ci.txt, then run the unit tests, ansible-lint, a syntax check, a
# check-mode run and two real runs against a synthetic inventory whose home is a
# scratch dir, and the role tests in tests/*.yml.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

# All test programs inherit an isolated home, even when invoked by a real runner.
: "${TMPDIR:?set TMPDIR to disk-backed scratch}"
export TMPDIR="$(realpath -m -- "$TMPDIR")"
case "$TMPDIR" in /*) ;; *) echo 'ci: scratch must be absolute' >&2; exit 1;; esac
case "$TMPDIR" in /tmp|/tmp/*|/|/home/igor) echo 'ci: unsafe scratch path' >&2; exit 1;; esac
case "$PWD/" in "$TMPDIR/"*) echo 'ci: scratch must not equal or contain the source root' >&2; exit 1;; esac
export HOME="$TMPDIR/fleet-test-home"
test "$HOME" = "$TMPDIR/fleet-test-home"
mkdir -p "$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_STATE_HOME="$HOME/.local/state"
export XDG_CACHE_HOME="$HOME/.cache" XDG_DATA_HOME="$HOME/.local/share"

python=${CI_PYTHON:-python3}
venv=.venv-ci
if ! cmp -s requirements-ci.txt "$venv/requirements-ci.txt"; then
	rm -rf "$venv"
	"$python" -m venv "$venv"
	"$venv/bin/pip" install --quiet --require-hashes --no-deps --only-binary=:all: -r requirements-ci.txt
	cp requirements-ci.txt "$venv/requirements-ci.txt"
fi
# tests/fake-bin holds a fake systemctl, so no run touches the user manager of
# the machine running CI.
export PATH="$PWD/tests/fake-bin:$PWD/$venv/bin:$PATH"
export FAKE_SYSTEMCTL_STATE="$PWD/.ci-home/systemctl.json"

reset_home() {
	rm -rf .ci-home
	mkdir -p .ci-home/data .ci-home/.ssh
	printf 'Host github-chaldea-fleet-config github-homelab-cli\n  HostName github.com\n' >.ci-home/.ssh/config
	printf '{"units": {}, "calls": []}\n' >"$FAKE_SYSTEMCTL_STATE"
}

python -m pytest -q -p no:cacheprovider tests
# Scratch may be inside an isolated job workspace; generated fixture plays are not source.
ansible-lint --exclude "$TMPDIR" --exclude "${TMPDIR#"$PWD"/}"
synthetic=(-i inventory -i tests/synthetic-inventory.yml --limit synthetic)
ansible-playbook "${synthetic[@]}" site.yml --syntax-check
reset_home
ansible-playbook "${synthetic[@]}" site.yml --check --diff

# Converge a fresh scratch home twice; the second run must change nothing.
# agent_tools needs the private repositories and t3 a running T3, so both stay
# in the check run above.
reset_home
ansible-playbook "${synthetic[@]}" site.yml --skip-tags agent_tools,t3
ansible-playbook "${synthetic[@]}" site.yml --skip-tags agent_tools,t3 | tee .ci-home/second-run.log
if ! grep -Eq '^synthetic +: ok=[0-9]+ +changed=0 ' .ci-home/second-run.log; then
	echo 'ci: the second run changed something; the play is not idempotent' >&2
	exit 1
fi

ansible-playbook -i localhost, tests/user_timer.yml
ansible-playbook -i localhost, tests/data_disk.yml
ansible-playbook -i localhost, tests/job_client.yml
