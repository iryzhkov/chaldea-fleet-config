"""The ordinary OpenCode Jocasta plugin: delivery, custody, removal and its contract.

Scratch homes and fake helper processes only. Nothing here runs the real helper,
reads an enrollment or qualifies native OpenCode on a host.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ["laptop", "agent-a", "agent-b", "omarchy-pc"]
MARKER = "// fleet-managed: webmcp-jocasta/v1\n"
PLUGIN = ".config/opencode/plugins/webmcp-jocasta.js"


def play(base, home, host="agent-a", *, state="present", enabled=True, qualified=True,
         user_dir=None, check=False):
    assert home.is_relative_to(base)
    inventory = base / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": {host: {
        "ansible_connection": "local", "ansible_python_interpreter": sys.executable}}}}))
    playbook = base / "opencode.yml"
    playbook.write_text(yaml.safe_dump([{
        "name": "Isolated OpenCode Jocasta plugin fixture",
        "hosts": "all", "gather_facts": False,
        "vars": {"fleet_home": str(home),
                 "ansible_facts": {"user_dir": user_dir or str(home), "user_uid": os.getuid()},
                 "webmcp_interactive_enabled": enabled,
                 "webmcp_interactive_laptop_qualified": qualified,
                 "webmcp_interactive_opencode_state": state},
        "tasks": [{"name": "Apply only the OpenCode plugin tasks", "ansible.builtin.include_role": {
            "name": "webmcp_interactive", "tasks_from": "opencode.yml"}}],
    }]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    return subprocess.run(["ansible-playbook", "-i", str(inventory), str(playbook)]
                          + (["--check", "--diff"] if check else []),
                          env=env, text=True, capture_output=True)


def neighbors(home):
    plugins = home / ".config/opencode/plugins"
    plugins.mkdir(parents=True)
    config = home / ".config/opencode/opencode.json"
    config.write_text(json.dumps({"model": "keep", "mcp": {"servers": {
        "unrelated": {"type": "remote", "url": "https://other.example/mcp"}}}}) + "\n")
    huyang = plugins / "huyang-profiles.js"
    huyang.write_text("// fleet-managed: huyang-profiles/v1\n")
    user = plugins / "user.js"
    user.write_text("// user owned\n")
    return {path: path.read_bytes() for path in (config, huyang, user)}


def declaration(host, home):
    return "const DECLARATION = Object.freeze(" + json.dumps(
        {"host": host, "uid": os.getuid(), "home": str(home)}) + ");\n"


@pytest.mark.parametrize("host", HOSTS)
def test_present_renders_this_host_and_is_idempotent(tmp_path, host):
    home = tmp_path / "home"
    before = neighbors(home)
    first = play(tmp_path, home, host)
    assert first.returncode == 0, first.stdout + first.stderr
    target = home / PLUGIN
    text = target.read_text()
    assert text.startswith(MARKER)
    assert declaration(host, home) in text
    assert target.stat().st_mode & 0o777 == 0o644
    second = play(tmp_path, home, host)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "changed=0" in second.stdout
    assert before == {path: path.read_bytes() for path in before}


def test_rendered_plugin_contract(tmp_path):
    home = tmp_path / "home"
    neighbors(home)
    result = play(tmp_path, home, "omarchy-pc")
    assert result.returncode == 0, result.stdout + result.stderr
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("OPENCODE_", "XDG_CONFIG_HOME"))}
    env.update(HOME=str(home), WEBMCP_JOCASTA_PLUGIN=str(home / PLUGIN), WEBMCP_JOCASTA_HOME=str(home),
               WEBMCP_JOCASTA_HOST="omarchy-pc", WEBMCP_JOCASTA_UID=str(os.getuid()))
    subprocess.run(["node", "--test", str(ROOT / "tests/webmcp-jocasta-plugin.test.mjs")],
                   env=env, check=True, cwd=tmp_path)


@pytest.mark.parametrize("case", [
    {"host": "homelab"}, {"host": "gaming-pc"}, {"enabled": False}, {"qualified": False},
    {"state": "enabled"}, {"user_dir": "/home/other"},
])
def test_present_refuses_without_its_preconditions(tmp_path, case):
    home = tmp_path / "home"
    neighbors(home)
    result = play(tmp_path, home, **case)
    assert result.returncode != 0
    assert not (home / PLUGIN).exists()


def test_laptop_needs_no_separate_qualification(tmp_path):
    home = tmp_path / "home"
    neighbors(home)
    result = play(tmp_path, home, "laptop", qualified=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / PLUGIN).exists()


def test_absent_removes_only_the_owned_plugin(tmp_path):
    home = tmp_path / "home"
    before = neighbors(home)
    assert play(tmp_path, home).returncode == 0
    # Rollback works after managed mode is disabled for this host.
    removed = play(tmp_path, home, state="absent", enabled=False, qualified=False)
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not (home / PLUGIN).exists()
    assert before == {path: path.read_bytes() for path in before}
    again = play(tmp_path, home, state="absent", enabled=False)
    assert again.returncode == 0 and "changed=0" in again.stdout


@pytest.mark.parametrize("state", ["present", "absent"])
@pytest.mark.parametrize("collision", ["unmarked", "file_symlink", "parent_symlink", "directory",
                                       "shared_writable", "hardlink"])
def test_unsafe_or_foreign_destinations_are_refused_untouched(tmp_path, state, collision):
    home = tmp_path / "home"
    neighbors(home)
    plugins = home / ".config/opencode/plugins"
    target = home / PLUGIN
    outside = tmp_path / "outside.js"
    outside.write_text(MARKER)
    if collision == "unmarked":
        target.write_text("// a user's own jocasta plugin\n")
    elif collision == "file_symlink":
        target.symlink_to(outside)
    elif collision == "parent_symlink":
        moved = tmp_path / "elsewhere"
        plugins.rename(moved)
        plugins.symlink_to(moved, target_is_directory=True)
    elif collision == "directory":
        target.mkdir()
    elif collision == "shared_writable":
        plugins.chmod(0o777)
    else:
        target.write_text(MARKER)
        os.link(target, tmp_path / "second-link.js")
    snapshot = {p: (p.is_symlink(), p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in [target, outside, *plugins.iterdir()] if p.exists() or p.is_symlink()}
    result = play(tmp_path, home, state=state)
    assert result.returncode != 0
    assert outside.read_text() == MARKER
    for path, (link, data) in snapshot.items():
        assert path.is_symlink() == link
        if data is not None:
            assert path.read_bytes() == data


def test_fresh_check_mode_creates_nothing(tmp_path):
    home = tmp_path / "fresh"
    (home / ".config").mkdir(parents=True)
    result = play(tmp_path, home, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Would install the fleet-owned OpenCode Jocasta plugin" in result.stdout
    assert not (home / ".config/opencode").exists()


def test_selection_is_explicit_standalone_and_laptop_only():
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults["webmcp_interactive_opencode_state"] == ""
    assert defaults["webmcp_interactive_enabled"] is False
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    names = [task["name"] for task in tasks]
    deliver = next(t for t in tasks if t["name"] == "Deliver or remove the ordinary OpenCode Jocasta plugin")
    assert deliver["when"] == "webmcp_interactive_opencode_state | default('') | length > 0"
    assert deliver["ansible.builtin.include_role"] == {
        "name": "webmcp_interactive", "tasks_from": "opencode.yml", "apply": {"tags": ["mcp_registrations"]}}
    assert names.index("Stage explicitly enabled managed interactive credentials and helper") \
        < names.index(deliver["name"])
    select = next(t for t in tasks if t["name"].startswith("Select explicit"))
    assert "'providers': ['claude', 'codex']" in select["ansible.builtin.set_fact"]["mcp_registrations_effective_remote_servers"]
    inventory = ROOT / "inventory"
    selections = {path.relative_to(inventory).as_posix()
                  for path in inventory.rglob("*.yml")
                  if "webmcp_interactive_opencode_state" in path.read_text()}
    assert selections == {"host_vars/laptop/jocasta-interactive.yml"}
    laptop = yaml.safe_load((inventory / "host_vars/laptop/jocasta-interactive.yml").read_text())
    assert laptop["webmcp_interactive_enabled"] is True
    assert laptop["webmcp_interactive_opencode_state"] == "present"
    main = (ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text()
    assert "opencode" not in main.lower()


def test_registration_module_still_refuses_an_opencode_helper():
    sys.path.insert(0, str(ROOT / "tests"))
    from test_mcp_registration import module_code
    assert module_code.HELPER_FIELDS == {"claude": "headersHelper", "codex": "http_headers_helper"}
