"""Resolve the selected stdio OV safety pin through the real inventory."""
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OLD = "efac1c8f04662a3512da84aa6559a26061e97832"
SAFE = "355a92adb0658853b7439e91d4429be3d0b270fc"


def test_only_laptop_and_omarchy_pc_select_safe_legacy_ov(tmp_path):
    common = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    assert common["agent_tools_ov_memory_ref"] == OLD
    expected_refs = {host: SAFE if host in {"laptop", "omarchy-pc"} else OLD
                     for host in ("agent-a", "agent-b", "laptop", "omarchy-pc", "homelab", "normandy")}
    inventory = subprocess.run(
        ["ansible-inventory", "-i", "inventory/hosts.yml", "--list"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    hosts = json.loads(inventory.stdout)["_meta"]["hostvars"]
    assert set(hosts) == set(expected_refs)
    for host, values in hosts.items():
        assert values["agent_tools_ov_memory_ref"] == expected_refs[host]
        assert values["agent_tools_sources"] == common["agent_tools_sources"]

    # Ansible resolves the catalog itself. No role, connection, credential or
    # native client is invoked; the only task is a controller-side assertion.
    play = {
        "hosts": "all", "gather_facts": False,
        "vars": {
            "expected_refs": expected_refs,
            "expected_sources": [
                {"name": "homelab-cli", "repo": "{{ agent_tools_homelab_cli_repo }}",
                 "ref": "f035d2820a28a523012078114005c30e8a0f00cc"},
                {"name": "ov-memory", "repo": "https://github.com/iryzhkov/ov-mcp.git",
                 "ref": "{{ expected_refs[inventory_hostname] }}"},
            ],
        },
        "tasks": [{"ansible.builtin.assert": {"that": [
            "agent_tools_sources == expected_sources",
        ]}}],
    }
    path = tmp_path / "ov-source-selection.yml"
    path.write_text(yaml.safe_dump([play]))
    result = subprocess.run(
        ["ansible-playbook", "-i", "inventory/hosts.yml", "--forks", "1", str(path)],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
