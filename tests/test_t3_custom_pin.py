"""Custom pin admission runs the canonical roles in scratch, with real /proc bytes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from test_chaldea_client import ROOT, fixture, provision, run, safe, success


@pytest.fixture
def pair(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    safe(tmp_path)
    home = Path.home()
    binary = home / ".t3/runtime/versions/0.0.45/t3"
    binary.parent.mkdir(parents=True)
    sleep = shutil.which("sleep")
    assert sleep is not None
    shutil.copyfile(sleep, binary)
    binary.chmod(0o755)
    process = subprocess.Popen([str(binary), "600"])
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    selection = home / ".t3/runtime/service-state.json"
    selection.write_text(json.dumps({"protocol": 3, "activeVersion": "0.0.45"}))
    runtime = home / ".t3/userdata/server-runtime.json"
    runtime.parent.mkdir()
    runtime.write_text(json.dumps({"pid": process.pid, "serverVersion": "0.0.45", "serviceManaged": True}))
    manager = tmp_path / "systemctl.json"
    state = json.loads(manager.read_text())
    state["units"]["t3code.service"] = {
        "enabled": True, "active": True,
        "properties": {
            "SubState": "running", "MainPID": str(process.pid),
            "ExecStart": "{ path=" + str(binary) + " ; argv[]=" + str(binary) + " __service-launcher ; }",
        },
    }
    manager.write_text(json.dumps(state))
    variables |= {
        "t3_version": "0.0.45", "t3_allow_upgrade": False,
        "t3_required_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "t3_custom_source": "a" * 40, "t3_custom_archive_sha256": "b" * 64,
    }
    try:
        yield variables, binary, selection, runtime, manager, other
    finally:
        for child in (process, other):
            child.terminate()
            child.wait(timeout=5)


def pull(base, variables, check=False):
    """Use the canonical site and inventory, limiting convergence to these roles."""
    safe(base)
    inventory = base / "pin-inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"agent_hosts": {"hosts": {
        "runtime-pin": variables | {"expected_hostname": "{{ ansible_facts.hostname }}"},
    }}}}}))
    return subprocess.run(
        ["ansible-playbook", "-i", str(ROOT / "inventory"), "-i", str(inventory),
         "--limit", "runtime-pin", str(ROOT / "site.yml"), "--tags", "chaldea_client,t3",
         *(["--check", "--diff"] if check else [])],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_matching_pair_check_real_second_preserves_identity(tmp_path, pair):
    variables, binary, selection, runtime, manager, _ = pair
    variables |= {"chaldea_client_quota_enabled": True, "chaldea_client_waits_enabled": True}
    provision()
    success(run(tmp_path, variables))
    client = Path.home() / ".local/share/chaldea/current"
    target = client.readlink()
    expected = (binary.read_bytes(), selection.read_bytes(), runtime.read_bytes())
    # Already activated pair: CHECK, REAL, SECOND are all read-only/idempotent.
    for check in (True, False, False):
        result = pull(tmp_path, variables, check=check)
        success(result)
        assert "changed=0" in result.stdout, result.stdout
        assert client.readlink() == target
        assert (binary.read_bytes(), selection.read_bytes(), runtime.read_bytes()) == expected
    calls = json.loads(manager.read_text())["calls"]
    assert all(call == ["show", "t3code.service"] for call in calls if "t3code.service" in call)


@pytest.mark.parametrize("case", [
    "wrong-binary", "absent-binary", "wrong-version", "wrong-selection",
    "absent-selection", "inactive", "wrong-exec-start", "wrong-live-launcher",
    "wrong-live-server", "wrong-server-version", "absent-runtime", "allow-upgrade",
])
@pytest.mark.parametrize("check", [False, True])
def test_bad_pair_refuses_before_client_mutation(tmp_path, pair, case, check):
    variables, binary, selection, runtime, manager, other = pair
    state = json.loads(manager.read_text())
    service = state["units"]["t3code.service"]
    if case == "wrong-binary":
        binary.unlink()
        binary.write_bytes(b"official or modified bytes with the same numeric version")
        binary.chmod(0o755)
    elif case == "absent-binary":
        binary.unlink()
    elif case == "wrong-version":
        variables["t3_version"] = "0.1.0"
    elif case == "wrong-selection":
        selection.write_text('{"activeVersion":"0.1.0"}')
    elif case == "absent-selection":
        selection.unlink()
    elif case == "inactive":
        service["active"] = False
    elif case == "wrong-exec-start":
        service["properties"]["ExecStart"] = service["properties"]["ExecStart"].replace("0.0.45", "0.1.0")
    elif case == "wrong-live-launcher":
        service["properties"]["MainPID"] = str(other.pid)
    elif case == "wrong-live-server":
        data = json.loads(runtime.read_text())
        runtime.write_text(json.dumps(data | {"pid": other.pid}))
    elif case == "wrong-server-version":
        data = json.loads(runtime.read_text())
        runtime.write_text(json.dumps(data | {"serverVersion": "0.1.0"}))
    elif case == "absent-runtime":
        runtime.unlink()
    elif case == "allow-upgrade":
        variables["t3_allow_upgrade"] = True
    manager.write_text(json.dumps(state))
    root = Path.home() / ".local/share/chaldea"
    previous = root / "releases/client-v0.4.11"
    previous.mkdir(parents=True)
    sentinel = previous / "retain"
    sentinel.write_bytes(b"prior client")
    (root / "current").symlink_to(previous)
    result = run(tmp_path, variables, check=check)
    assert result.returncode != 0, result.stdout
    assert "changed=0" in result.stdout, result.stdout
    assert (root / "current").readlink() == previous
    assert sentinel.read_bytes() == b"prior client"
    assert list((root / "releases").iterdir()) == [previous]
    assert not (Path.home() / ".cache/chaldea-client").exists()
    assert not (Path.home() / ".config/chaldea").exists()
    assert all(call == ["show", "t3code.service"] for call in json.loads(manager.read_text())["calls"])


def test_only_omarchy_inventory_selects_custom_pair():
    inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    shared = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    defaults = yaml.safe_load((ROOT / "roles/t3/defaults/main.yml").read_text())
    hosts = inventory["all"]["children"]["agent_hosts"]["hosts"]
    assert defaults["t3_required_binary_sha256"] == ""
    assert shared["t3_version"] == "0.1.0"
    assert shared["chaldea_client_version"] == "client-v0.4.11"
    pc = hosts["omarchy-pc"]
    assert pc["t3_version"] == "0.0.45"
    assert pc["t3_required_binary_sha256"] == "18c808e79a4c84ba64e0ef1e064de94838f22789f0dc650e8b5cddff33dae495"
    assert pc["t3_custom_source"] == "161de7bb3e948490fd8af5b0da16c034067a5685"
    assert pc["t3_custom_archive_sha256"] == "ad50546a2bce82ae04b8fd57cc75e9df97bdd3965dc5c7a08320904ba4bee403"
    assert pc["chaldea_client_version"] == "client-v0.4.17"
    assert pc["chaldea_client_sha256"] == "81a1c1860ff3194a288fa4518bfca3e46dbc732ee23c872aebb6382afbd50839"
    for name, values in hosts.items():
        if name != "omarchy-pc":
            assert not {"t3_version", "t3_required_binary_sha256", "t3_custom_source",
                        "t3_custom_archive_sha256", "chaldea_client_version", "chaldea_client_sha256"} & values.keys()


def test_official_t3_default_keeps_existing_behavior(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    variables["t3_version"] = "0.1.0"
    state = Path.home() / ".t3/runtime/service-state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"activeVersion":"0.1.0"}')
    manager = tmp_path / "systemctl.json"
    data = json.loads(manager.read_text())
    data["units"]["t3code.service"] = {"active": True, "enabled": True}
    manager.write_text(json.dumps(data))
    play = tmp_path / "official.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Official T3 pin in scratch", "hosts": "localhost",
        "connection": "local", "gather_facts": False, "vars": variables, "roles": ["t3"],
    }]))
    for check in (True, False):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", str(play), *(["--check"] if check else [])],
            cwd=ROOT, env=dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles")),
            capture_output=True, text=True,
        )
        success(result)
        assert "changed=0" in result.stdout
        assert "server-runtime.json" not in result.stdout
