"""Exercise the CI runner's actual arguments against pytest collection."""
import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
PHASES = WORKFLOW["jobs"]["checks"]["strategy"]["matrix"]["phase"]
PYTEST_PHASES = [p for p in PHASES if p.startswith("pytest-")]


@pytest.fixture
def runner(tmp_path):
    root = tmp_path / "runner"
    (root / "tools").mkdir(parents=True)
    shutil.copyfile(ROOT / "tools/ci.sh", root / "tools/ci.sh")
    (root / "requirements-ci.txt").write_text("fixture lock")
    venv = root / ".venv-ci"
    (venv / "bin").mkdir(parents=True)
    shutil.copyfile(root / "requirements-ci.txt", venv / "requirements-ci.txt")
    python = venv / "bin/python"
    python.write_text(f"""#!{sys.executable}
import json, os, sys
from pathlib import Path
assert os.environ['HOME'] == os.environ['TMPDIR'] + '/fleet-test-home'
Path(os.environ['RECORD']).write_text(json.dumps(dict(
    args=sys.argv[1:], home=os.environ['HOME'], tmp=os.environ['TMPDIR'])))
sys.exit(int(os.environ.get('PYTEST_EXIT', '0')))
""")
    python.chmod(0o755)
    for name in ("node", "mise"):
        program = venv / "bin" / name
        program.write_text("#!/bin/sh\nexit 0\n")
        program.chmod(0o755)

    def run(phase, exit_code=0):
        scratch = tmp_path / phase
        record = tmp_path / (phase + ".json")
        env = dict(os.environ, TMPDIR=str(scratch), RECORD=str(record),
                   PYTEST_EXIT=str(exit_code),
                   PATH=str(venv / "bin") + os.pathsep + os.environ["PATH"])
        result = subprocess.run(["bash", str(root / "tools/ci.sh"), phase],
                                env=env, text=True, capture_output=True)
        return result, json.loads(record.read_text())
    return run


def collect(args, cwd):
    result = subprocess.run(
        [sys.executable, *args, "--collect-only"], cwd=cwd,
        text=True, capture_output=True)
    assert result.returncode in (0, 5), result.stdout + result.stderr
    return [line for line in result.stdout.splitlines() if "::" in line]


def assert_partition(baseline, lanes):
    flattened = [node for lane in lanes for node in lane]
    assert collections.Counter(flattened) == collections.Counter(baseline)
    assert len(flattened) == len(set(flattened))
    # Every parameterized case from a file must stay in the same lane.
    owners = collections.defaultdict(set)
    for index, lane in enumerate(lanes):
        for node in lane:
            owners[node.split("::")[0]].add(index)
    assert all(len(indices) == 1 for indices in owners.values())


def test_real_collection_and_future_directories_are_partitioned(runner, tmp_path):
    args = []
    homes = []
    for phase in PYTEST_PHASES:
        result, record = runner(phase)
        assert result.returncode == 0, result.stderr
        args.append(record["args"])
        homes.append(record["home"])
        assert not (Path(record["tmp"]) / "host-artifact-vars.json").exists()
        assert not (Path(record["tmp"]) / "client-artifact-vars.json").exists()
    assert len(set(homes)) == len(PYTEST_PHASES) == 5
    baseline = collect(["-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], ROOT)
    lanes = [collect(a, ROOT) for a in args]
    assert_partition(baseline, lanes)
    print(f"CI partition: {len(baseline)} node IDs, lanes {[len(x) for x in lanes]}")

    future = tmp_path / "future"
    tests = future / "tests"
    # Existing explicit targets must exist, but contain no future cases.
    for path in ROOT.joinpath("tests").rglob("test_*.py"):
        target = tests / path.relative_to(ROOT / "tests")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")
    for name in ("test_future.py", "new/deeper/test_future.py", "new/deeper/future_test.py"):
        target = tests / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('import pytest\n@pytest.mark.parametrize("x", [1, 2])\ndef test_future(x): pass\n')
    future_baseline = collect(["-m", "pytest", "-q", "tests", "--import-mode=importlib"], future)
    future_lanes = [collect(a + ["--import-mode=importlib"], future) for a in args]
    assert len(future_baseline) == 6
    assert_partition(future_baseline, future_lanes)
    assert future_lanes[-1] == future_baseline


@pytest.mark.parametrize("phase", PYTEST_PHASES + ["pytest-rest"])
def test_pytest_failure_propagates(runner, phase):
    result, _ = runner(phase, exit_code=17)
    assert result.returncode == 17


def test_aggregate_requires_every_matrix_lane_and_helper():
    jobs = WORKFLOW["jobs"]
    assert jobs["checks"]["strategy"]["fail-fast"] is False
    assert "converge" in PHASES
    aggregate = jobs["ci"]
    assert aggregate["if"] == "always()"
    assert set(aggregate["needs"]) == {"checks", "managed-helper"}
    step = aggregate["steps"][0]
    assert step["env"] == {
        "CHECKS_RESULT": "${{ needs.checks.result }}",
        "HELPER_RESULT": "${{ needs.managed-helper.result }}",
    }
    for checks in ("success", "failure", "cancelled", "skipped"):
        for helper in ("success", "failure", "cancelled", "skipped"):
            result = subprocess.run(["bash", "-c", step["run"]],
                                    env=dict(os.environ, CHECKS_RESULT=checks, HELPER_RESULT=helper))
            assert (result.returncode == 0) == (checks == helper == "success")
