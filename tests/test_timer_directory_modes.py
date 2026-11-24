"""Exercise the real directory tasks in site.yml order in a scratch home."""
import os
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]


def directory_tasks(role, filename="main.yml"):
    tasks = yaml.safe_load((ROOT / "roles" / role / "tasks" / filename).read_text())
    return [task for task in tasks
            if task.get("ansible.builtin.file", {}).get("state") == "directory"]


def test_timer_and_rotation_directories_converge_together(tmp_path):
    home = Path.home()
    assert home.is_relative_to(tmp_path.parent)
    assert tmp_path.is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    reporting = directory_tasks("timer_reporting")
    rotation = directory_tasks("host_credential_rotation", "manage.yml")
    timer = directory_tasks("user_timer")
    play = tmp_path / "directories.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Timer directory ownership regression", "hosts": "localhost",
        "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(home),
                 "user_timer_unit_dir": str(home / ".config/systemd/user")},
        # retention, rotation and pull_timer all use this shared directory.
        "tasks": reporting + timer + rotation + timer + reporting + timer,
    }]))
    command = ["ansible-playbook", "-i", "localhost,", str(play)]

    def run(*args):
        result = subprocess.run(command + list(args), capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    run()
    unit_directory = home / ".config/systemd/user"
    private_directory = home / ".local/lib/chaldea-rotation"
    assert unit_directory.stat().st_mode & 0o777 == 0o755
    assert private_directory.stat().st_mode & 0o777 == 0o700
    assert re.search(r"changed=0\s", run("--check", "--diff"))
    assert re.search(r"changed=0\s", run())

    # Permission repair remains observable; do not suppress real changes.
    private_directory.chmod(0o755)
    assert re.search(r"changed=1\s", run("--check", "--diff"))
    assert private_directory.stat().st_mode & 0o777 == 0o755
    assert re.search(r"changed=1\s", run())
    assert private_directory.stat().st_mode & 0o777 == 0o700
    assert re.search(r"changed=0\s", run())
