"""Exercise the new selection/composition boundary with public-only inputs."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import types
import urllib.request

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "access-trust/akasha-enrollment.json").read_text())
SPEC = importlib.util.spec_from_file_location("enrollment_pull", ROOT / "tools/akasha-enrollment-pull.py")
assert SPEC and SPEC.loader
PULL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PULL)


def public_inputs() -> dict:
    keys = {host: dict(kty="OKP", crv="Ed25519", x=base64.urlsafe_b64encode(bytes([i]) * 32).decode().rstrip("="))
            for i, host in enumerate(POLICY, 1)}
    keys["agent-a"] = json.loads((ROOT / "access-trust/issuer-grants.json").read_text())[0]["public_key"]
    return dict(public_keys=keys, pc_reader=False, pc_quota=False)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("published-client")
    assert scratch.is_relative_to(Path(os.environ["TMPDIR"]))
    version = "client-v0.4.0"
    url = "https://github.com/iryzhkov/chaldea/releases/download/" + version + "/"
    for name in ("chaldea-client.tar.gz", "manifest.json"):
        with urllib.request.urlopen(url + name, timeout=90) as response:
            (scratch / name).write_bytes(response.read())
    expected = "fc80729f9179340c7a29ff1eac5a310aea013ddb107633e4f9b2f1250691dc8d"
    assert hashlib.sha256((scratch / "chaldea-client.tar.gz").read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location("release", ROOT / "library/chaldea_client_release.py")
    assert spec and spec.loader
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    release.install(types.SimpleNamespace(check_mode=False, params=dict(root=str(scratch / "releases"),
        version=version, archive=str(scratch / "chaldea-client.tar.gz"), manifest=str(scratch / "manifest.json"), sha256=expected)))
    return scratch / "releases" / version


def compose(client, data):
    return subprocess.run(["node", str(ROOT / "tools/akasha-enrollment-inputs.mjs"), str(client),
                           str(ROOT / "access-trust/akasha-enrollment.json"), str(ROOT / "access-trust/issuer-grants.json")],
                          input=json.dumps(data), text=True, capture_output=True)


def test_exact_local_selection_and_no_passthrough(tmp_path):
    path = tmp_path / "public.json"
    path.write_text(json.dumps({"akasha_enrollment_public_keys": public_inputs()["public_keys"]}))
    for host, row in POLICY.items():
        args = [host, "a" * 40, str(path), "stage", "--check"]
        cmd = PULL.command(args, host, row["uid"], row["home"])
        assert cmd[cmd.index("--limit") + 1] == host and cmd[-1] == "playbooks/akasha-enrollment.yml"
        assert "--check" in cmd and "site.yml" not in cmd and "--tags" not in cmd
        for wrong in ((host, 0, row["home"]), ("other", row["uid"], row["home"]), (host, row["uid"], "/root")):
            with pytest.raises(ValueError):
                PULL.command(args, *wrong)
    for host in ("all", "agent-*", "homelab,agent-a", "normandy", "laptop"):
        with pytest.raises(ValueError):
            PULL.command([host, "a" * 40, str(path), "stage"], host, 1000, "/home/igor")
    path.write_text('{"akasha_enrollment_public_keys":{}}')
    with pytest.raises(ValueError):
        PULL.command(["agent-a", "a" * 40, str(path), "stage"], "agent-a", 1000, "/home/igor")


@pytest.mark.parametrize("fault", ["missing", "private", "bad", "duplicate", "reuse"])
def test_canonical_key_rejections(client, fault):
    data = public_inputs()
    keys = data["public_keys"]
    if fault == "missing":
        del keys["agent-b"]
    elif fault == "private":
        keys["agent-b"]["d"] = "private-material-is-forbidden"
    elif fault == "bad":
        keys["agent-b"]["x"] = "invalid"
    elif fault == "duplicate":
        keys["agent-b"] = keys["homelab"]
    else:
        keys["agent-a"] = dict(kty="OKP", crv="Ed25519", x="A" * 43)
    assert compose(client, data).returncode != 0


def test_fixed_native_outputs_preserve_old_records_and_bound_pc(client):
    old = json.loads((ROOT / "access-trust/issuer-grants.json").read_text())
    result = compose(client, public_inputs())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["issuers"][0]["ceilings"][:3] == old[0]["ceilings"]
    assert all(not r.get("global_read") and r["source"] != "chaldea-quota" for r in data["registry"])
    assert all(g["action"] == "append" for grants in data["grants"].values() for g in grants)
    enabled = compose(client, public_inputs() | dict(pc_reader=True, pc_quota=True))
    assert enabled.returncode == 0, enabled.stderr
    records = json.loads(enabled.stdout)
    optional = [r for r in records["registry"] if r["source"] in ("fleet-reader", "chaldea-quota")]
    assert len(optional) == 2 and all(r["host"] == "omarchy-pc" for r in optional)
    assert len(next(r for r in optional if r["source"] == "chaldea-quota")["kinds"]) == 7


def test_disabled_play_and_missing_inputs_have_no_install_effects(tmp_path):
    env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"))
    args = ["ansible-playbook", "-i", str(ROOT / "inventory/akasha-enrollment.yml"), "--limit", "agent-a",
            str(ROOT / "playbooks/akasha-enrollment.yml")]
    disabled = subprocess.run(args, env=env, text=True, capture_output=True)
    assert disabled.returncode == 0 and "TASK [Gather only" not in disabled.stdout
    missing = subprocess.run(args + ["-e", '{"akasha_enrollment_enabled":true}'], env=env, text=True, capture_output=True)
    assert missing.returncode != 0 and "Require one exact" in missing.stdout and "Gather only" not in missing.stdout

@pytest.mark.parametrize("state,rc,passes", [
    ("LoadState=loaded\\nActiveState=active\\nUnitFileState=disabled", 0, False),
    ("LoadState=loaded\\nActiveState=inactive\\nUnitFileState=enabled", 0, False),
    ("LoadState=loaded\\nActiveState=inactive\\nUnitFileState=disabled", 0, True),
    ("LoadState=not-found\\nActiveState=inactive\\nUnitFileState=", 0, True),
    ("", 1, False)])
def test_staging_refuses_existing_activation_without_stopping_it(tmp_path, state, rc, passes):
    tasks = yaml.safe_load((ROOT / "playbooks/akasha-enrollment.yml").read_text())[0]["pre_tasks"]
    selected = [t for t in tasks if t["name"] in ("Inspect existing collector timer state without changing it",
                                                "Refuse staging over an active or enabled collector")]
    fake = tmp_path / "systemctl"
    fake.write_text("#!/bin/sh\nprintf '" + state + "\\n'\nexit " + str(rc) + "\n")
    fake.chmod(0o755)
    play = tmp_path / "stage.yml"
    play.write_text(yaml.safe_dump([dict(name="Check staging", hosts="localhost", gather_facts=False,
        vars={"akasha_enrollment_activate": False}, tasks=selected)]))
    env = dict(os.environ, PATH=str(tmp_path) + ":" + os.environ["PATH"],
               ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)],
                            env=env, text=True, capture_output=True)
    assert (result.returncode == 0) is passes, result.stdout
    assert "changed=0" in result.stdout

def test_activation_refuses_inventory_that_would_undo_it(tmp_path):
    task = next(t for t in yaml.safe_load((ROOT / "playbooks/akasha-enrollment.yml").read_text())[0]["pre_tasks"]
                if t["name"] == "Require persistent fleet inventory agreement before activation")
    task = dict(task)
    task.pop("vars")
    task.pop("when")
    play = tmp_path / "persistent.yml"
    play.write_text(yaml.safe_dump([dict(name="Protect activation", hosts="localhost", gather_facts=False,
        vars=dict(akasha_enrollment_normal_host={}, akasha_collector_url="https://akasha.ryzhkov.dev",
                  akasha_collector_token_helper="/usr/local/bin/chaldea-token-helper"), tasks=[task])]))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)],
        env=dict(os.environ, ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote")),
        text=True, capture_output=True)
    assert result.returncode != 0 and "next normal fleet pull would undo" in result.stdout and "changed=0" in result.stdout
