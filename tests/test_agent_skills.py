"""Exercise the skill retirement and link migration against disposable homes."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "roles/agent_config/files/skills"
RETIRED = (
    "find-skills", "improve-codebase-architecture", "domain-modeling",
    "prototype", "code-review", "implementation-session",
)
DIRECTORIES = (".claude/skills", ".agents/skills")


def scratch():
    home = Path.home().resolve()
    assert home.is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    assert home.name.startswith("home-")  # Supplied by isolated_home, never the operator.
    return home


def run_role(home, task_file, skills=None, check=False, succeeds=True, host="localhost", uid=None):
    play = scratch() / "skills-play.yml"
    variables = {
        "ansible_connection": "local",
        "ansible_python_interpreter": sys.executable,
        "fleet_home": str(home),
        "ansible_facts": {"user_uid": os.getuid() if uid is None else uid, "user_gid": os.getgid()},
    }
    if skills is not None:
        variables["agent_config_skills"] = skills
    play.write_text(yaml.safe_dump([{
        "name": "Exercise skill ownership in scratch",
        "hosts": host, "gather_facts": False,
        "vars": variables,
        "tasks": [{
            "name": "Run the real skill tasks",
            "ansible.builtin.include_role": {
                "name": "agent_config", "tasks_from": task_file,
            },
        }],
    }]))
    environment = {
        **os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
        "ANSIBLE_LOCAL_TEMP": str(scratch() / "ansible"),
    }
    argv = ["ansible-playbook", "-i", host + ",", str(play)]
    if check:
        argv.append("--check")
    result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, text=True)
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == succeeds, output
    return output


def test_retire_only_exact_real_directories():
    home = scratch() / "fleet"
    protected = scratch() / "protected"
    protected.mkdir()
    (protected / "keep").write_text("target must survive")
    for directory in DIRECTORIES:
        root = home / directory
        root.mkdir(parents=True)
        for name in ("safety-critical-code", "synced", "unslop", "code-review-extra"):
            (root / name).mkdir()
            (root / name / "keep").write_text(name)
        for name in RETIRED:
            path = root / name
            if directory == ".claude/skills":
                path.mkdir()
                (path / "old").write_text(name)
                (path / "linked-target").symlink_to(protected, target_is_directory=True)
            else:
                path.symlink_to(protected, target_is_directory=True)

    run_role(home, "retire-skills", check=True)
    assert all((home / DIRECTORIES[0] / name / "old").exists() for name in RETIRED)
    run_role(home, "retire-skills")
    assert all(not (home / DIRECTORIES[0] / name).exists() for name in RETIRED)
    assert all((home / DIRECTORIES[1] / name).is_symlink() for name in RETIRED)
    assert (protected / "keep").read_text() == "target must survive"
    for directory in DIRECTORIES:
        for name in ("safety-critical-code", "synced", "unslop", "code-review-extra"):
            assert (home / directory / name / "keep").read_text() == name

    # Regular files with retired names also remain untouched.
    for name in RETIRED:
        (home / DIRECTORIES[0] / name).write_text("not a directory")
    assert re.search(r"changed=0\s", run_role(home, "retire-skills"))
    assert all((home / DIRECTORIES[0] / name).read_text() == "not a directory" for name in RETIRED)


def laptop_layout():
    home = scratch() / "fleet"
    claude = home / ".claude/skills"
    agents = home / ".agents/skills"
    claude.mkdir(parents=True)
    agents.mkdir(parents=True)
    for name in ("safety-critical-code", "unslop"):
        shutil.copytree(SKILLS / name, agents / name)
        (claude / name).symlink_to(agents / name, target_is_directory=True)
    # synced is a store, not an installable skill.
    store = scratch() / "sync-store"
    store.mkdir()
    (store / "keep").write_text("unmanaged")
    (claude / "synced").symlink_to(store, target_is_directory=True)
    return home, claude, agents, store


def test_identical_laptop_links_become_managed_copies():
    home, claude, agents, store = laptop_layout()
    names = ["safety-critical-code", "unslop"]
    run_role(home, "install-skills", skills=names, check=True)
    assert all((claude / name).is_symlink() for name in names)
    run_role(home, "install-skills", skills=names)
    for directory in (claude, agents):
        for name in names:
            assert (directory / name).is_dir() and not (directory / name).is_symlink()
            for source in (SKILLS / name).rglob("*"):
                if source.is_file():
                    installed = directory / name / source.relative_to(SKILLS / name)
                    assert installed.read_bytes() == source.read_bytes()
    assert (claude / "synced").is_symlink()
    assert (store / "keep").read_text() == "unmanaged"
    assert re.search(r"changed=0\s", run_role(home, "install-skills", skills=names))


@pytest.mark.parametrize("difference", ["changed", "extra", "missing", "file", "unhandled"])
def test_mismatched_or_unhandled_links_stop_before_unlink(difference):
    home, claude, agents, store = laptop_layout()
    names = ["safety-critical-code", "unslop"]
    target = agents / "unslop"
    if difference == "changed":
        (target / "SKILL.md").write_text("local changes must survive")
    elif difference == "extra":
        (target / "local.md").write_text("extra file must survive")
    elif difference == "missing":
        (target / "SKILL.md").unlink()
    elif difference == "file":
        (claude / "unslop").unlink()
        (claude / "unslop").symlink_to(target / "SKILL.md")
    else:
        (claude / "tdd").symlink_to(store, target_is_directory=True)
        names.append("tdd")

    for check in (True, False):
        run_role(home, "install-skills", skills=names, check=check, succeeds=False)
        # A valid first link is not replaced when any later validation fails.
        assert all((claude / name).is_symlink() for name in names)
        assert (claude / "synced").is_symlink()
        assert (store / "keep").read_text() == "unmanaged"
    if difference == "changed":
        assert (target / "SKILL.md").read_text() == "local changes must survive"
    elif difference == "extra":
        assert (target / "local.md").read_text() == "extra file must survive"
    elif difference == "missing":
        assert not (target / "SKILL.md").exists()
