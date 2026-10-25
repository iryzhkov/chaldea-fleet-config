"""The installed launcher uses the pinned Node, preserves CLI arguments and sends
only `chaldea exec` to an optional, separately admitted client."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "roles/chaldea_job_client/templates/chaldea.j2"
# The launcher template exactly as it was before exec-only selection existed.
BASE_LAUNCHER = ROOT / "tests/fixtures/chaldea-launcher-base.j2"
NODE_VERSION = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())["chaldea_node_version"]
# ansible.builtin.template drops the newline after a block tag and keeps the final one.
JINJA = Environment(undefined=StrictUndefined, trim_blocks=True, keep_trailing_newline=True)
ENV_KEYS = ("HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "CHALDEA_FIXTURE")
REFUSAL = "Set chaldea_job_client_exec_entry and chaldea_job_client_exec_node together"


def scratch(path):
    tmp = Path(os.environ["TMPDIR"]).resolve()
    assert tmp != Path("/tmp") and not tmp.is_relative_to("/tmp")
    assert path.resolve().is_relative_to(tmp)
    assert Path.home().resolve().is_relative_to(tmp) and Path.home() != Path("/home/igor")


def render(template, **variables):
    return JINJA.from_string(template.read_text()).render(chaldea_node_version=NODE_VERSION, **variables)


def invoke(home, *args, extra_env=None, **variables):
    launcher = home / "launcher"
    launcher.write_text(render(LAUNCHER, **variables))
    return run_launcher(launcher, home, args, extra_env)


def run_launcher(launcher, home, args, extra_env=None):
    return subprocess.run(["sh", str(launcher), *args],
                          env={**os.environ, "HOME": str(home), **(extra_env or {})},
                          capture_output=True, text=True)


def fake_node(path, label, markers):
    """A Node stand-in that records that it ran, then reports argv and environment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                    f"open({str(markers / label)!r}, 'a').write('ran\\n')\n"
                    f"print(json.dumps({{'node': {label!r}, 'argv': sys.argv[1:], "
                    f"'env': {{k: os.environ.get(k) for k in {ENV_KEYS!r}}}}}))\n"
                    "sys.stderr.write('fixture stderr\\n')\n"
                    "sys.exit(23)\n")
    path.chmod(0o755)


def runtimes(home, *, release="current", pinned=True, entry=True, node=True):
    """Install the pinned release and an admitted exec client, both synthetic."""
    scratch(home)
    markers = home / "markers"
    markers.mkdir(parents=True, exist_ok=True)
    paths = {"markers": markers,
             "pinned_entry": home / f".local/share/chaldea/{release}/bin/chaldea",
             "pinned_node": home / f".local/share/mise/installs/node/{NODE_VERSION}/bin/node",
             "entry": home / "admitted/client-fixture/bin/chaldea",
             "node": home / "admitted/node-fixture"}
    if pinned:
        paths["pinned_entry"].parent.mkdir(parents=True)
        paths["pinned_entry"].write_text("pinned fixture")
        fake_node(paths["pinned_node"], "pinned", markers)
    if entry:
        paths["entry"].parent.mkdir(parents=True)
        paths["entry"].write_text("admitted fixture")
    if node:
        fake_node(paths["node"], "selected", markers)
    return paths


def selection(paths):
    return {"chaldea_client_enabled": True,
            "chaldea_job_client_exec_entry": str(paths["entry"]),
            "chaldea_job_client_exec_node": str(paths["node"])}


def ran(paths):
    return sorted(p.name for p in paths["markers"].iterdir())


def test_launcher_explains_a_missing_app_checkout(tmp_path):
    result = invoke(tmp_path, "exec", "--host", "agent-a", "--", "true")
    assert result.returncode == 69
    assert "app checkout is missing" in result.stderr
    assert str(tmp_path / ".local/share/chaldea/app") in result.stderr


def test_launcher_explains_a_missing_pinned_node(tmp_path):
    entry = tmp_path / ".local/share/chaldea/app/bin/chaldea"
    entry.parent.mkdir(parents=True)
    entry.write_text("fixture")
    result = invoke(tmp_path, "wait", "--help")
    assert result.returncode == 69
    assert f"pinned Node {NODE_VERSION} is missing" in result.stderr


@pytest.mark.parametrize("args", [
    ["exec", "--host", "agent-a", "--", "printf", "two words", "$HOME", ""],
    ["wait", "time", "--after", "30s", "--thread", "thread:fixture"],
    ["decision", "ask", "--question", "Run this step?", "--option", "Defer"],
])
def test_launcher_uses_bin_dispatcher_and_preserves_status_and_arguments(tmp_path, args):
    paths = runtimes(tmp_path, release="app", entry=False, node=False)

    result = invoke(tmp_path, *args)

    assert result.returncode == 23
    assert json.loads(result.stdout)["argv"] == [str(paths["pinned_entry"]), *args]
    assert result.stderr == "fixture stderr\n"


@pytest.mark.parametrize("client_enabled", [False, True])
def test_default_launcher_is_byte_identical_to_the_base_template(client_enabled):
    base = render(BASE_LAUNCHER, chaldea_client_enabled=client_enabled)
    assert render(LAUNCHER, chaldea_client_enabled=client_enabled) == base
    assert render(LAUNCHER, chaldea_client_enabled=client_enabled,
                  chaldea_job_client_exec_entry="", chaldea_job_client_exec_node="") == base


@pytest.mark.parametrize("args", [
    ["exec"],
    ["exec", "--host", "agent-a", "--", "printf", "two words", "$HOME", "", "it's", "*;|&`id`", "a\nb"],
    ["exec", "--artifact", "out dir/result.txt", "--", "sh", "-c", "exit 3"],
    ["exec", "show", "fixture-job", "--full"],
])
def test_selected_exec_runs_only_the_admitted_client(tmp_path, args):
    paths = runtimes(tmp_path)
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config dir"), "XDG_STATE_HOME": str(tmp_path / "state"),
           "CHALDEA_FIXTURE": "kept $literal"}

    result = invoke(tmp_path, *args, extra_env=env, **selection(paths))

    assert result.returncode == 23
    report = json.loads(result.stdout)
    assert report["node"] == "selected"
    assert report["argv"] == [str(paths["entry"]), *args]
    assert report["env"] == {"HOME": str(tmp_path), "XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME"), **env}
    assert result.stderr == "fixture stderr\n"
    assert ran(paths) == ["selected"]


def test_selected_exec_does_not_need_the_pinned_release(tmp_path):
    paths = runtimes(tmp_path, pinned=False)
    result = invoke(tmp_path, "exec", "--", "true", **selection(paths))
    assert result.returncode == 23
    assert ran(paths) == ["selected"]


@pytest.mark.parametrize("args", [
    [], ["--describe"], ["--help"], ["wait", "--help"], ["quota", "status", "--json"],
    ["route", "--role", "builder"], ["artifacts", "publish"], ["execute"], ["EXEC"], [" exec"],
    ["--host", "agent-a", "exec"], ["", "exec"],
])
def test_selection_keeps_every_other_command_on_the_pinned_release(tmp_path, args):
    paths = runtimes(tmp_path)

    result = invoke(tmp_path, *args, **selection(paths))

    assert result.returncode == 23
    report = json.loads(result.stdout)
    assert report["node"] == "pinned"
    assert report["argv"] == [str(paths["pinned_entry"]), *args]
    assert ran(paths) == ["pinned"]


def test_selection_keeps_the_pinned_release_refusal_for_other_commands(tmp_path):
    paths = runtimes(tmp_path, pinned=False)
    result = invoke(tmp_path, "wait", "--help", **selection(paths))
    assert result.returncode == 69
    assert "client release is missing" in result.stderr
    assert ran(paths) == []


@pytest.mark.parametrize("broken", ["entry", "entry-directory", "node", "node-not-executable", "node-directory"])
def test_selected_exec_fails_closed_without_falling_back(tmp_path, broken):
    paths = runtimes(tmp_path, entry=broken not in ("entry", "entry-directory"),
                     node=broken not in ("node", "node-directory"))
    if broken == "entry-directory":
        paths["entry"].mkdir(parents=True)
    elif broken == "node-directory":
        paths["node"].mkdir(parents=True)
    elif broken == "node-not-executable":
        paths["node"].chmod(0o644)

    result = invoke(tmp_path, "exec", "--", "true", **selection(paths))

    assert result.returncode == 69
    assert result.stdout == ""
    assert "refusing to fall back to the pinned release" in result.stderr
    assert str(paths["entry" if broken.startswith("entry") else "node"]) in result.stderr
    assert ran(paths) == []


# The remaining tests apply the real roles with ansible-playbook in scratch.

def playbook(tmp_path, variables, tasks):
    scratch(tmp_path)
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{"name": "Launcher in scratch", "hosts": "localhost",
                                    "connection": "local", "gather_facts": False,
                                    "vars": {"ansible_python_interpreter": sys.executable,
                                             "chaldea_node_version": NODE_VERSION, **variables},
                                    "tasks": tasks}]))
    return subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)], cwd=ROOT,
                          env={**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                               "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible")},
                          capture_output=True, text=True)


ROLE = [{"name": "Apply the launcher role", "ansible.builtin.include_role": {"name": "chaldea_job_client"}}]


@pytest.mark.parametrize("client_enabled", [False, True])
def test_role_renders_the_base_launcher_bytes_by_default(tmp_path, client_enabled):
    home = tmp_path / "home"
    result = playbook(tmp_path, {"fleet_home": str(home), "chaldea_client_enabled": client_enabled}, ROLE + [{
        "name": "Render the base launcher with the real template module",
        "ansible.builtin.template": {"src": str(BASE_LAUNCHER), "dest": str(tmp_path / "base"), "mode": "0755"}}])
    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / ".local/bin/chaldea").read_bytes() == (tmp_path / "base").read_bytes()


def test_role_installs_a_valid_selection_idempotently(tmp_path):
    home = tmp_path / "home"
    paths = runtimes(home)
    variables = {"fleet_home": str(home), **selection(paths)}
    for attempt in range(2):
        result = playbook(tmp_path, variables, ROLE)
        assert result.returncode == 0, result.stdout + result.stderr
        assert ("changed=0" in result.stdout) == (attempt == 1), result.stdout
    launcher = home / ".local/bin/chaldea"
    text = launcher.read_text()
    assert f"chaldea_entry='{paths['entry']}'" in text and f"chaldea_node='{paths['node']}'" in text
    assert launcher.stat().st_mode & 0o777 == 0o755
    args = ["exec", "--host", "agent-a", "--", "printf", "two words", "it's"]
    result = run_launcher(launcher, home, args)
    assert result.returncode == 23
    assert json.loads(result.stdout)["argv"] == [str(paths["entry"]), *args]
    assert run_launcher(launcher, home, ["--describe"]).returncode == 23
    assert ran(paths) == ["pinned", "selected"]


@pytest.mark.parametrize("selected", [
    {"chaldea_job_client_exec_entry": "/opt/fixture/bin/chaldea"},
    {"chaldea_job_client_exec_node": "/opt/fixture/node"},
    {"chaldea_job_client_exec_entry": "opt/fixture/bin/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/fixture/bin/chaldea", "chaldea_job_client_exec_node": "~/node"},
    {"chaldea_job_client_exec_entry": "/opt/two words/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/it's/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/$HOME/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/fixture/bin/chaldea", "chaldea_job_client_exec_node": "/opt/node\n"},
    {"chaldea_job_client_exec_entry": "/opt/../bin/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/./bin/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt//bin/chaldea", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/bin/", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": "/opt/node", "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": None, "chaldea_job_client_exec_node": "/opt/node"},
    {"chaldea_job_client_exec_entry": ["/opt/bin/chaldea"], "chaldea_job_client_exec_node": "/opt/node"},
])
def test_role_refuses_an_unsafe_selection_before_any_change(tmp_path, selected):
    home = tmp_path / "home"
    result = playbook(tmp_path, {"fleet_home": str(home), "chaldea_client_enabled": True, **selected}, ROLE)
    assert result.returncode != 0
    assert REFUSAL in result.stdout, result.stdout + result.stderr
    assert not home.exists()


def test_launcher_tag_converges_only_validation_and_the_launcher(tmp_path):
    """The launcher tag must skip SSH enrollment, which would refuse the absent key,
    and every client release, current-link and user-service task."""
    scratch(tmp_path)
    home = tmp_path / "home"
    paths = runtimes(home)
    before = {p for p in home.rglob("*")}
    manager = tmp_path / "systemctl.json"
    manager.write_text(json.dumps({"units": {}, "calls": []}))
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"agent_hosts": {"hosts": {"fixture": {
        "ansible_connection": "local",
        "ansible_python_interpreter": sys.executable,
        "expected_hostname": socket.gethostname().split(".")[0],
        "fleet_home": str(home),
        "chaldea_node_version": NODE_VERSION,
        "chaldea_job_client_enabled": True,
        "chaldea_job_client_targets": [{"name": "fixture", "address": "192.0.2.123", "port": 2222}],
        **selection(paths),
    }}}}}}))
    result = subprocess.run(["ansible-playbook", "-i", str(inventory), str(ROOT / "site.yml"),
                             "--limit", "fixture", "--tags", "chaldea_exec_launcher"], cwd=ROOT,
                            env={**os.environ, "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible"),
                                 "PATH": str(ROOT / "tests/fake-bin") + ":" + os.environ["PATH"],
                                 "FAKE_SYSTEMCTL_STATE": str(manager)},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    tasks = {line.split("[", 1)[1].rsplit("]", 1)[0] for line in result.stdout.splitlines()
             if line.startswith("TASK [")}
    assert tasks == {"Gathering Facts", "Refuse to apply another host's configuration",
                     "chaldea_job_client : Validate the optional exec-only client selection",
                     "chaldea_job_client : Create the local CLI directory",
                     "chaldea_job_client : Install the pinned Chaldea launcher"}, result.stdout
    launcher = home / ".local/bin/chaldea"
    assert {p for p in home.rglob("*")} - before == {launcher.parent, launcher}
    assert f"chaldea_entry='{paths['entry']}'" in launcher.read_text()
    assert json.loads(manager.read_text())["calls"] == []
