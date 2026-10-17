"""Render both services and ask systemd to verify them without starting units."""

import os
import shutil
import subprocess
from pathlib import Path

import jinja2
import pytest
import yaml

from test_retention_unit import render

ROOT = Path(__file__).resolve().parents[1]


def test_pull_arguments_and_failure_dependency():
    template = ROOT / "roles/pull_timer/templates/chaldea-fleet-pull.service.j2"
    unit = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(template.read_text()).render(
        pull_timer_venv="/home/u/ansible", pull_timer_repo="git@example.invalid:repo",
        pull_timer_branch="main", pull_timer_checkout="/home/u/checkout", inventory_hostname="host")
    assert "OnFailure=chaldea-timer-failure@chaldea-fleet-pull.service" in unit
    assert "run --job chaldea-fleet-pull --checkout /home/u/checkout -- /home/u/ansible/bin/ansible-pull" in unit
    assert "--limit host" in unit and "TimeoutStartSec=1h" in unit


def test_systemd_accepts_services_and_failure_handler(tmp_path):
    analyzer = shutil.which("systemd-analyze")
    if not analyzer:
        pytest.skip("systemd-analyze unavailable")
    wrapper = tmp_path / ".local/bin/chaldea-timer-report"
    wrapper.parent.mkdir(parents=True)
    wrapper.symlink_to("/bin/true")
    tasks = yaml.safe_load((ROOT / "roles/timer_reporting/tasks/main.yml").read_text())
    handler = next(task["ansible.builtin.copy"]["content"] for task in tasks
                   if task["name"] == "Install the timer failure handler")
    units = {
        "chaldea-retention.service": render(True),
        "chaldea-timer-failure@.service": handler,
    }
    template = (ROOT / "roles/pull_timer/templates/chaldea-fleet-pull.service.j2").read_text()
    units["chaldea-fleet-pull.service"] = jinja2.Template(template).render(
        pull_timer_venv="/unused/ansible", pull_timer_repo="git@example.invalid:repo",
        pull_timer_branch="main", pull_timer_checkout="/unused/checkout", inventory_hostname="host")
    for name, content in units.items():
        (tmp_path / name).write_text(content.replace("%h", str(tmp_path)))
    environment = os.environ.copy()
    environment["SYSTEMD_UNIT_PATH"] = str(tmp_path) + ":"
    environment["XDG_RUNTIME_DIR"] = str(tmp_path)
    result = subprocess.run([analyzer, "--user", "verify", "--man=no",
                             str(tmp_path / "chaldea-retention.service"),
                             str(tmp_path / "chaldea-fleet-pull.service"),
                             str(tmp_path / "chaldea-timer-failure@chaldea-retention.service")],
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TimeoutStartSec=30s" in handler
