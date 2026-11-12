"""Retired units stop before removal; repeated convergence leaves state alone."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scope", ["system", "user"])
@pytest.mark.parametrize("installed", [False, True])
def test_cleanup_is_idempotent_and_preserves_state(tmp_path, monkeypatch, scope, installed):
    home = Path.home()
    assert home.is_relative_to(Path(os.environ["TMPDIR"]))
    source = yaml.safe_load((ROOT / "roles/retired_services/tasks/main.yml").read_text())
    tasks = [task for task in source if scope in task["name"].split()]
    units = tasks[0]["loop"]
    unit_dir = home / ".config/systemd/user"
    unit_dir.mkdir(parents=True)
    # Both scopes use the isolated fake manager and unit directory in this test.
    tasks[0]["ansible.builtin.stat"]["path"] = str(unit_dir) + "/{{ item }}"
    for task in tasks:
        task["become"] = False
        if "ansible.builtin.systemd_service" in task:
            task["ansible.builtin.systemd_service"]["scope"] = "user"
    if installed:
        for name in units:
            (unit_dir / name).write_text("[Service]\nExecStart=/fixture\n")
    state_dir = home / ".local/state/chaldea"
    state_dir.mkdir(parents=True)
    sentinel = state_dir / "archive-sentinel"
    sentinel.write_bytes(b"preserve")
    before = sentinel.stat()
    manager = tmp_path / "manager.json"
    manager.write_text(json.dumps({"calls": [], "units": {
        name: {"active": True, "enabled": True} for name in units if installed}}))
    monkeypatch.setenv("PATH", str(ROOT / "tests/fake-bin") + ":" + os.environ["PATH"])
    monkeypatch.setenv("FAKE_SYSTEMCTL_STATE", str(manager))
    monkeypatch.setenv("FAKE_SYSTEMCTL_UNIT_HOME", str(home))
    play = tmp_path / "cleanup.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Retire units in scratch", "hosts": "localhost",
        "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(home), "ansible_python_interpreter": sys.executable},
        "tasks": tasks}]))
    for attempt in range(2):
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        if attempt or not installed:
            assert "changed=0" in result.stdout
    assert all(not (unit_dir / name).exists() for name in units)
    states = json.loads(manager.read_text())
    assert all(not unit["active"] and not unit["enabled"] for unit in states["units"].values())
    assert sentinel.read_bytes() == b"preserve"
    assert sentinel.stat().st_ino == before.st_ino
    assert sentinel.stat().st_mtime_ns == before.st_mtime_ns
