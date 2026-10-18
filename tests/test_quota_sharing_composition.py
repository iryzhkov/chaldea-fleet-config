"""Exercise optional sharing guards and actual scoped configuration writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = yaml.safe_load((ROOT / "playbooks/tasks/akasha-quota-preflight.yml").read_text())


def run(tmp_path, host, tasks, values, state="inactive", enabled="disabled", unit="quota.json"):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    assert tmp_path.is_relative_to(Path(os.environ["TMPDIR"]))
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    (fake / "systemctl").write_text("#!/bin/sh\nprintf '%s\\n' 'LoadState=loaded' 'ActiveState=" +
        state + "' 'UnitFileState=" + enabled + "' 'ExecStart=/current/bin/chaldea --quota-config " +
        str(tmp_path / ".config/chaldea" / unit) + "'\n")
    (fake / "systemctl").chmod(0o755)
    playdir = tmp_path / "playbooks"
    playdir.mkdir(exist_ok=True)
    play = playdir / "test.yml"
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    play.write_text(yaml.safe_dump([dict(hosts=host, connection="local", gather_facts=False,
        vars=defaults | dict(fleet_home=str(tmp_path), chaldea_node_version="26.10.0",
            akasha_enrollment_host=dict(uid=os.getuid()), akasha_collector_url="https://akasha.ryzhkov.dev",
            akasha_collector_token_helper="/usr/local/bin/chaldea-token-helper") | values, tasks=tasks)]))
    env = dict(os.environ, PATH=str(fake) + ":" + os.environ["PATH"],
               ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"))
    return subprocess.run(["ansible-playbook", "-i", host + ",", str(play)], env=env, text=True, capture_output=True)


@pytest.mark.parametrize("state,enabled,passes", [
    ("active", "disabled", False), ("inactive", "enabled", False), ("inactive", "disabled", True)])
def test_laptop_normal_observer_must_be_disabled_and_inactive(tmp_path, state, enabled, passes):
    result = run(tmp_path, "omarchy-macbook-air-igor", PREFLIGHT[:2],
                 dict(akasha_quota_normal_host=dict(chaldea_client_quota_enabled=False)), state, enabled)
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    assert "changed=0" in result.stdout


@pytest.mark.parametrize("fleet,unit,persistent,passes", [
    (False, "quota.json", True, True), (True, "quota.json", True, False),
    (False, "quota-sharing.json", True, False), (False, "quota.json", False, False)])
def test_pc_reader_never_turns_actual_observer_into_publisher(tmp_path, fleet, unit, persistent, passes):
    directory = tmp_path / ".config/chaldea"
    directory.mkdir(parents=True)
    (directory / "quota.json").write_text(json.dumps(dict(fleet=dict(enabled=fleet))))
    before = (directory / "quota.json").read_bytes()
    result = run(tmp_path, "omarchy-pc", [PREFLIGHT[0], *PREFLIGHT[-2:]],
        dict(akasha_quota_normal_host=dict(chaldea_client_route_targets=dict(
            quotaConfigFile=str(directory / "quota-fleet-reader.json") if persistent else ""))), unit=unit)
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    assert (directory / "quota.json").read_bytes() == before


def test_scoped_sharing_writes_preserve_normal_files_and_next_normal_render(tmp_path):
    role = tmp_path / "roles/chaldea_client"
    shutil.copytree(ROOT / "roles/chaldea_client/templates", role / "templates")
    directory = tmp_path / ".config/chaldea"
    directory.mkdir(parents=True)
    units = tmp_path / ".config/systemd/user"
    units.mkdir(parents=True)
    normal = {directory / "events.json": '{"url":"cutover","tokenHelper":"/fixed/helper"}\n',
              directory / "quota.json": '{"contexts":[],"fleet":{"enabled":false}}\n',
              units / "chaldea-quota.service": "normal observer\n"}
    for path, text in normal.items():
        path.write_text(text)
    source = yaml.safe_load((ROOT / "playbooks/tasks/akasha-quota-sharing.yml").read_text())
    tasks = [task for task in source if "ansible.builtin.file" in task or "ansible.builtin.copy" in task
             or "ansible.builtin.template" in task]
    values = dict(akasha_quota_runtime_version="client-v0.4.2")
    result = run(tmp_path, "omarchy-macbook-air-igor", tasks, values)
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(path.read_text() == text for path, text in normal.items())
    child = directory / "quota-sharing-runtime/chaldea"
    assert json.loads((child / "events.json").read_text()) == {}
    restart = json.loads((child / "restart.json").read_text())
    assert restart == dict(enabled=False, journalPath=str(tmp_path / ".local/state/chaldea/quota-sharing/restart.sqlite"))
    sharing = json.loads((directory / "quota-sharing.json").read_text())
    assert sharing["contexts"] == [] and "claudeContexts" not in sharing
    assert sharing["fleet"] == dict(enabled=True, host="omarchy-macbook-air-igor",
        url="https://akasha.ryzhkov.dev", tokenHelper="/usr/local/bin/chaldea-token-helper",
        cacheFile=str(tmp_path / ".local/state/chaldea/quota-sharing/publish-cache.json"))
    new = {path: path.read_bytes() for path in [child / "events.json", child / "restart.json",
           directory / "quota-sharing.json", units / "chaldea-quota-sharing.service"]}
    again = run(tmp_path, "omarchy-macbook-air-igor", tasks, values)
    assert again.returncode == 0 and "changed=0" in again.stdout, again.stdout + again.stderr
    ordinary = [dict(name="Normal role observer render", **{"ansible.builtin.template": dict(
        src=str(role / "templates/chaldea-quota.service.j2"), dest=str(units / "chaldea-quota.service"), mode="0644")})]
    normal_pull = run(tmp_path, "omarchy-macbook-air-igor", ordinary, {})
    assert normal_pull.returncode == 0, normal_pull.stdout + normal_pull.stderr
    assert all(path.read_bytes() == text for path, text in new.items())
    assert "/current/bin/chaldea" in (units / "chaldea-quota.service").read_text()
    assert "quota-sharing" not in (units / "chaldea-quota.service").read_text()
