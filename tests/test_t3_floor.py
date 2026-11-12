"""Run the actual T3 gate in normal and check mode without a live service."""
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize("active,floor,passes", [
    ("0.1.6", "0.1.6", True),
    ("0.1.9", "0.1.6", True),
    ("0.1.10", "0.1.6", True),
    ("0.1.6", "0.1.7", False),
    ("0.1.5", "0.1.6", False),
])
def test_minimum_version_gate(tmp_path, check, active, floor, passes):
    tasks = yaml.safe_load((ROOT / "roles/t3/tasks/main.yml").read_text())
    gate = next(t for t in tasks if t["name"] == "Assert T3 meets the minimum version")
    home = tmp_path / "home"
    home.mkdir()
    play = tmp_path / "floor.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"t3_active_version": active, "t3_min_version": floor},
        "tasks": [gate],
    }]))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"),
               ANSIBLE_NOCOLOR="1")
    assert Path(env["HOME"]) == home
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
        + (["--check"] if check else []),
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=45,
    )
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    if not passes:
        assert f"T3 is {active} but the minimum is {floor}" in result.stdout
