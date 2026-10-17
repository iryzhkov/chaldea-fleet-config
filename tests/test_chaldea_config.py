"""Chaldea registration compatibility, opt-in and role convergence."""

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, call

ROOT = Path(__file__).resolve().parents[1]


def chaldea(home):
    return {
        "name": "chaldea",
        "command": f"{home}/.local/share/mise/installs/node/26.10.0/bin/node",
        "args": [f"{home}/.local/share/chaldea/app/src/cli.ts", "mcp", "--config",
                 f"{home}/.config/chaldea/waits.json"],
    }


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_existing_omarchy_registration_is_unchanged(tmp_path, provider):
    # Exact command/args and absence of extra options observed read-only with
    # claude mcp get chaldea and codex mcp get chaldea --json on omarchy-pc.
    desired = chaldea("/home/igor")
    path = tmp_path / ("claude.json" if provider == "claude" else "config.toml")
    if provider == "claude":
        path.write_text(json.dumps({"chaldea": {
            "type": "stdio", "command": desired["command"], "args": desired["args"],
        }}))
        params = {"claude_command": [FAKE_CLAUDE, str(path)]}
    else:
        path.write_text('[mcp_servers.chaldea]\ncommand = ' + json.dumps(desired["command"])
                        + '\nargs = ' + json.dumps(desired["args"]) + '\n')
        params = {"codex_config": str(path)}
    before = path.read_bytes()

    assert not call(provider, **params, **desired)["changed"]
    assert path.read_bytes() == before


def test_waits_are_opted_in_only_on_omarchy_pc():
    inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    defaults = yaml.safe_load((ROOT / "roles/mcp_registrations/defaults/main.yml").read_text())
    assert defaults["mcp_registrations_chaldea_waits_enabled"] is False
    enabled = [
        host
        for group in inventory["all"]["children"].values()
        for host, values in group["hosts"].items()
        if values.get("mcp_registrations_chaldea_waits_enabled", False)
    ]
    assert enabled == ["omarchy-pc"]


def test_role_gates_chaldea_for_both_providers_and_converges(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    codex = home / ".codex/config.toml"
    claude = home / "claude.json"
    codex.write_text('model = "personal"\n[mcp_servers.other]\ncommand = "/keep"\n')
    claude.write_text(json.dumps({"other": {"type": "stdio", "command": "/keep"}}))
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Exercise MCP registration in an isolated home",
        "hosts": "localhost",
        "gather_facts": False,
        "vars": {
            "ansible_connection": "local",
            "ansible_python_interpreter": sys.executable,
            "fleet_home": str(home),
            "mcp_registrations_claude": [FAKE_CLAUDE, str(claude)],
        },
        "roles": ["mcp_registrations"],
    }]))
    environment = {**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                   "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible")}

    def run(enabled=None, check=False):
        argv = ["ansible-playbook", "-i", "localhost,", str(play)]
        if enabled is not None:
            argv += ["-e", json.dumps({"mcp_registrations_chaldea_waits_enabled": enabled})]
        if check:
            argv += ["--check"]
        result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def definitions():
        return json.loads(claude.read_text()), tomllib.loads(codex.read_text())["mcp_servers"]

    run()  # Default hosts must not acquire the registration.
    assert all("chaldea" not in servers for servers in definitions())
    run(True)
    expected = chaldea(str(home))
    a, b = definitions()
    assert a["chaldea"] == {"type": "stdio", "command": expected["command"],
                             "args": expected["args"], "env": {}}
    assert b["chaldea"] == {"command": expected["command"], "args": expected["args"]}
    assert re.search(r"changed=0\s", run(True))

    before = claude.read_bytes(), codex.read_bytes()
    run(False, check=True)
    assert (claude.read_bytes(), codex.read_bytes()) == before
    run(False)  # Turning the switch off removes an existing registration.
    a, b = definitions()
    assert "chaldea" not in a and "chaldea" not in b
    assert a["other"]["command"] == b["other"]["command"] == "/keep"
    assert tomllib.loads(codex.read_text())["model"] == "personal"
    assert re.search(r"changed=0\s", run())
