"""A client management hold preserves installed-client MCP selection."""
import json
import os
from pathlib import Path
import platform
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_management_hold_skips_client_and_preserves_registration(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"agent_hosts": {
        "hosts": {"held": {
            "ansible_connection": "local",
            "expected_hostname": platform.node().split(".")[0],
            "fleet_home": str(home),
            "chaldea_client_enabled": True,
            "chaldea_client_manage": False,
            # Invalid pins must never reach the client role under a hold.
            "chaldea_client_version": "must-not-run",
        }},
    }}}}))
    play = tmp_path / "hold.yml"
    play.write_text(yaml.safe_dump([
        {"import_playbook": str(ROOT / "site.yml")},
        {"hosts": "held", "gather_facts": False, "tasks": [
            {"ansible.builtin.include_vars":
             str(ROOT / "roles/mcp_registrations/defaults/main.yml")},
            {"ansible.builtin.assert": {"that": [
                "(mcp_registrations_servers | selectattr('name', 'equalto', 'chaldea') | first).enabled | bool",
                "'/current/bin/chaldea' in (mcp_registrations_servers | selectattr('name', 'equalto', 'chaldea') | first).args[0]",
            ]}},
        ], "tags": ["chaldea_client"]},
    ], sort_keys=False))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"))
    assert Path(env["HOME"]) == home
    result = subprocess.run(
        ["ansible-playbook", "-i", str(ROOT / "inventory"), "-i", str(inventory),
         "--limit", "held", "--tags", "chaldea_client", str(play)],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed=0" in result.stdout
    assert not (home / ".local/share/chaldea").exists()
