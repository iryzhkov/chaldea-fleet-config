import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fleet_tools", ROOT / "roles/agent_config/files/fleet_tools.py")
assert spec is not None and spec.loader is not None
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)


def executable(tmp_path, name, data=None, body=None):
    path = tmp_path / name
    if body is None:
        payload = json.dumps(data)
        body = "#!/usr/bin/python3\nimport sys\nassert sys.argv[1:] == ['--describe']\nprint(" + repr(payload) + ")\n"
    path.write_text(body)
    path.chmod(0o755)
    return path


def metadata(name, commands=None):
    return {"name": name, "summary": "Fixture tool", "help": name + " --help",
            "commands": commands or [{"name": "inspect", "summary": "Inspect", "access": "read"},
                                     {"name": "mutate", "summary": "Mutate", "access": "write"}]}


def profile(tools, mcp=None):
    return {"name": "fixture", "tools": tools, "mcp": mcp or []}


def test_grants_filter_tools_commands_and_mcp(tmp_path):
    tools = {name: executable(tmp_path, name, metadata(name)) for name in ("feed", "pve", "jocasta")}
    # An explicit empty grant overrides wildcard grants.
    output = fleet.render(tools, profile({"*": ["read"], "pve": [], "jocasta": ["write"]}))
    assert "inspect" in output and "jocasta" in output
    assert output.count("mutate") == 1
    assert "`pve`" not in output and "ov-memory" not in output
    assert "write: mutate" not in next(line for line in output.splitlines() if line.startswith("- `feed`"))
    assert "ov-memory" in fleet.render({}, profile({}, ["ov-memory"]))
    assert "- `" not in fleet.render(tools, profile({}))


def test_not_granted_is_never_executed(tmp_path):
    tool = executable(tmp_path, "feed", body="#!/bin/sh\ntouch '" + str(tmp_path / "ran") + "'\n")
    fleet.render({"feed": tool}, profile({}))
    assert not (tmp_path / "ran").exists()


@pytest.mark.parametrize("body", ["#!/bin/sh\nexit 1\n", "#!/bin/sh\nprintf 'bad json'\n",
                                 "#!/bin/sh\nprintf '[]'\n"])
def test_failures_are_name_only_and_nonfatal(tmp_path, body):
    path = executable(tmp_path, "feed", body=body)
    output = fleet.render({"feed": path}, profile({"feed": ["read"]}))
    assert "feed" in output and "description unavailable" in output


def test_timeout_and_bad_classification_are_unavailable(tmp_path, monkeypatch):
    path = executable(tmp_path, "feed", metadata("feed", [{"name": "bad", "summary": "Bad", "access": "maybe"}]))
    assert fleet.describe(path) is None
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("fixture", 5)
    monkeypatch.setattr(fleet.subprocess, "run", timeout)
    assert "description unavailable" in fleet.render({"feed": path}, profile({"feed": ["read"]}))


def test_discovery_uses_installed_executables_and_stays_compact(tmp_path):
    for number in range(22):
        executable(tmp_path, "tool" + str(number), metadata("tool" + str(number)))
    (tmp_path / "not-executable").write_text("ignored")
    tools = fleet.installed_tools([str(tmp_path), str(tmp_path / "missing")], [])
    assert len(tools) == 22
    output = fleet.render(tools, profile({"*": ["read", "write"]}, ["ov-memory"]))
    assert len(output.splitlines()) < 60
    assert output == fleet.render(tools, profile({"*": ["read", "write"]}, ["ov-memory"]))


def test_jocasta_mcp_grant_adds_only_its_guidance_line():
    plain = fleet.render({}, profile({}, ["ov-memory"]))
    granted = fleet.render({}, profile({}, ["ov-memory", "jocasta"]))
    assert "jocasta" not in plain
    assert granted.startswith(plain)
    assert granted[len(plain):] == ("\n## Working documents\n- `jocasta` MCP: shared working documents through the enrolled "
                                    "native registration; read `~/.config/agents/jocasta.md` for outline, section and "
                                    "guarded edit use.\n")
    for unknown in (["jocasta_tooling"], ["huyang"]):
        with pytest.raises(ValueError, match="unknown MCP grant"):
            fleet.render({}, profile({}, unknown))


def test_bad_profiles_fail_closed():
    for value in ({}, {"name": "restricted", "tools": {"*": ["execute"]}, "mcp": []}):
        with pytest.raises(ValueError):
            fleet.render({}, value)


def test_role_converges_same_filtered_skill_for_all_providers(tmp_path):
    home = tmp_path / "fleet-home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable(fake_bin, "feed", metadata("feed"))
    executable(fake_bin, "pve", metadata("pve"))  # Not selected for installation.
    play = tmp_path / "play.yml"
    # Include only the renderer tasks: no real host services or config touched.
    play.write_text(json.dumps([{
        "name": "Fixture fleet tools", "hosts": "all", "gather_facts": False,
        "vars": {"fleet_home": str(home),
                 "agent_config_fleet_tools_profile": profile({"*": ["read"]}),
                 "agent_tools_homelab_cli_commands": ["feed"],
                 "agent_tools_bin_dir": str(fake_bin)},
        "tasks": [{"name": "Render tools", "ansible.builtin.include_role":
                   {"name": "agent_config", "tasks_from": "fleet-tools"}}],
    }]))
    import os
    env = {**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles")}
    command = ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
    for attempt in range(2):
        result = subprocess.run(command, text=True, capture_output=True, env=env, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        if attempt:
            assert "changed=0" in result.stdout
    outputs = [(home / directory / "fleet-tools/SKILL.md").read_text()
               for directory in (".claude/skills", ".agents/skills", ".codex/skills")]
    assert len(set(outputs)) == 1
    assert "inspect" in outputs[0] and "mutate" not in outputs[0]
    assert "`pve`" not in outputs[0]
    invalid = json.loads(play.read_text())
    invalid[0]["vars"]["agent_config_fleet_tools_profile"] = profile({"feed": ["execute"]})
    play.write_text(json.dumps(invalid))
    result = subprocess.run(command, text=True, capture_output=True, env=env, timeout=60)
    assert result.returncode != 0
    for directory in (".claude/skills", ".agents/skills", ".codex/skills"):
        content = (home / directory / "fleet-tools/SKILL.md").read_text()
        assert "No tool descriptions: profile unavailable." in content
        assert "inspect" not in content and "mutate" not in content
