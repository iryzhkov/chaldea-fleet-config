"""Exercise the actual native settings merge without a live T3 service."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("initial", [None, {}, {"autoResumeLimitedThreads": False},
                                    {"autoResumeLimitedThreads": True}])
def test_settings_merge_preserves_preferences_and_metadata(tmp_path, initial):
    home = tmp_path / "home"
    settings = home / ".t3/userdata/settings.json"
    settings.parent.mkdir(parents=True)
    if initial is not None:
        initial = initial | {"favorites": [{"model": "keep"}], "futureKey": {"keep": 7}}
        settings.write_text(json.dumps(initial))
        settings.chmod(0o640)
    before = settings.stat() if settings.exists() else None
    play = tmp_path / "settings.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"t3_home": str(home / ".t3")},
        "tasks": [{"name": "Apply native settings",
                   "ansible.builtin.include_tasks": str(ROOT / "roles/t3/tasks/settings.yml")}],
    }]))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"))
    assert Path(env["HOME"]) == home

    def run(check=False):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
            + (["--check"] if check else []),
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    run(check=True)
    assert (json.loads(settings.read_text()) if settings.exists() else None) == initial
    run()
    assert json.loads(settings.read_text()) == (initial or {}) | {"autoResumeLimitedThreads": True}
    after = settings.stat()
    if before:
        assert (after.st_mode, after.st_uid, after.st_gid) == (
            before.st_mode, before.st_uid, before.st_gid)
        if initial is not None and initial.get("autoResumeLimitedThreads") is True:
            assert after.st_mtime_ns == before.st_mtime_ns
    else:
        assert after.st_mode & 0o777 == 0o600
    assert "changed=0" in run()
    assert settings.stat().st_mtime_ns == after.st_mtime_ns
