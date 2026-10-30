"""Regression for Ansible 2.19 trusted normal-inventory composition."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml
from test_quota_sharing_composition import ROOT, PREFLIGHT, run

def test_real_inventory_patch_resolves_pc_reader_and_account_bindings(tmp_path):
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    shutil.copyfile(ROOT / "inventory/hosts.yml", inventory / "hosts.yml")
    host_vars = inventory / "host_vars/omarchy-pc"
    host_vars.mkdir(parents=True)
    shutil.copyfile(ROOT / "inventory/host_vars/omarchy-pc/fate-route.yml", host_vars / "fate-route.yml")
    patch = subprocess.run(["patch", "-p1", "-i", str(ROOT / "docs/akasha-quota-sharing-inventory.patch")],
                           cwd=tmp_path, capture_output=True, text=True)
    assert patch.returncode == 0, patch.stdout + patch.stderr
    # The legacy enrollment guard reads hosts.yml; ordinary pulls also load host_vars.
    # The optional patch must select the same quota reader through both paths.
    effective = subprocess.run(["ansible-inventory", "-i", str(inventory / "hosts.yml"),
                                "--host", "omarchy-pc"], check=True, capture_output=True, text=True)
    targets = json.loads(effective.stdout)["chaldea_client_route_targets"]
    assert targets["quotaConfigFile"].endswith("/.config/chaldea/quota-fleet-reader.json")
    assert targets["scores"]["enabled"] is True
    assert targets["benchmark"]["indexVersion"] == "5"
    assert targets["announceHost"] == "homelab"
    role = tmp_path / "roles/chaldea_client"
    shutil.copytree(ROOT / "roles/chaldea_client/templates", role / "templates")
    directory = tmp_path / ".config/chaldea"
    directory.mkdir(parents=True)
    (directory / "quota.json").write_text('{"fleet":{"enabled":false}}')
    original = yaml.safe_load((ROOT / "playbooks/vars/akasha-enrollment.yml").read_text())
    values = {k:v for k,v in original.items() if k.startswith("akasha_quota_normal_")}
    reader = next(t for t in yaml.safe_load((ROOT / "playbooks/tasks/akasha-quota-sharing.yml").read_text())
                  if t["name"] == "Render only the PC router reader file with its normal account contexts")
    result = run(tmp_path, "omarchy-pc", PREFLIGHT + [reader], values)
    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads((directory / "quota-fleet-reader.json").read_text())
    assert config["contexts"][0]["codexHome"] == str(tmp_path / ".codex")
    for context in config.get("claudeContexts", []):
        assert context["envFile"] == str(tmp_path / ".config/claude/oauth.env")
    assert "{{" not in json.dumps(config)


@pytest.mark.parametrize("host", ["omarchy-pc", "agent-a", "agent-b", "laptop"])
def test_normal_quota_unit_hardening_from_actual_inventory(tmp_path, host):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    assert tmp_path.is_relative_to(Path(os.environ["TMPDIR"]))
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    assert defaults["chaldea_client_quota_no_new_privileges"] is True
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert hosts["omarchy-pc"]["chaldea_client_quota_no_new_privileges"] is False
    assert all("chaldea_client_quota_no_new_privileges" not in values
               for name, values in hosts.items() if name != "omarchy-pc")
    play = tmp_path / "render.yml"
    play.write_text(yaml.safe_dump([dict(
        hosts=host, connection="local", gather_facts=False,
        vars=dict(fleet_home=str(tmp_path), ansible_facts=dict(user_uid=os.getuid())),
        tasks=[
            dict(name="Expose role defaults without enabling the isolated runtime",
                 **{"ansible.builtin.include_role": dict(
                     name="chaldea_client", tasks_from="quota-runtime", public=True)}),
            dict(name="Render actual normal observer unit",
                 **{"ansible.builtin.template": dict(
                     src=str(ROOT / "roles/chaldea_client/templates/chaldea-quota.service.j2"),
                     dest=str(tmp_path / "chaldea-quota.service"), mode="0644")}),
            dict(name="Render default hardening for byte comparison",
                 vars=dict(chaldea_client_quota_no_new_privileges=True),
                 **{"ansible.builtin.template": dict(
                     src=str(ROOT / "roles/chaldea_client/templates/chaldea-quota.service.j2"),
                     dest=str(tmp_path / "default.service"), mode="0644")}),
        ])]))
    result = subprocess.run(["ansible-playbook", "-i", str(ROOT / "inventory"), str(play)],
                            cwd=ROOT, capture_output=True, text=True,
                            env=dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles")))
    assert result.returncode == 0, result.stdout + result.stderr
    actual = (tmp_path / "chaldea-quota.service").read_bytes()
    default = (tmp_path / "default.service").read_bytes()
    assert default.count(b"NoNewPrivileges=yes\n") == 1
    assert actual == (default.replace(b"NoNewPrivileges=yes\n", b"NoNewPrivileges=no\n")
                      if host == "omarchy-pc" else default)
    assert b"/current/bin/chaldea quota observe" in actual
    assert b"quota-sharing" not in actual
