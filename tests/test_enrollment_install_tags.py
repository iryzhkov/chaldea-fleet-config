"""The helper-only tag must reach included role tasks."""
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_install_tag_runs_helper_only(tmp_path):
    source = yaml.safe_load((ROOT / "playbooks/akasha-enrollment.yml").read_text())[0]
    include = next(t for t in source["tasks"] if t["name"] == "Install the canonical root-owned helper")
    role = tmp_path / "roles/chaldea_token_helper/tasks"
    role.mkdir(parents=True)
    (role / "main.yml").write_text(yaml.safe_dump([
        {"name": "Helper sentinel", "ansible.builtin.debug": {"msg": "HELPER_RAN"}}]))
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "tasks": [include, {"name": "Collector sentinel",
                           "ansible.builtin.fail": {"msg": "collector must not run"},
                           "tags": ["enrollment_activate"]}],
    }]))
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"),
               ANSIBLE_NOCOLOR="1")
    assert Path(env["HOME"]) == home
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play),
         "--tags", "enrollment_install", "--check"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HELPER_RAN" in result.stdout
