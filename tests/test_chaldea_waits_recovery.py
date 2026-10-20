"""Real Ansible restart orchestration with a bounded fake daemon, in scratch only."""
import copy
import json
import os
from pathlib import Path
import socket

import pytest
import yaml

from test_chaldea_client import safe
from test_chaldea_waits_system import ROLE, TEMPLATES, play


FAKE_MANAGER = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state_path = Path(os.environ["WAITS_RECOVERY_STATE"])
state = json.loads(state_path.read_text())
words = [word for word in sys.argv[1:] if not word.startswith("-")]
verb = words[0] if words else ""
rc = 0
if "--version" in sys.argv:
    print("systemd 257 (257)")
elif verb == "show":
    unit = Path(os.environ["WAITS_RECOVERY_UNIT"]).read_text()
    command = next(line.split("=", 1)[1] for line in unit.splitlines() if line.startswith("ExecStart="))
    print("Id=chaldea-waits.service\nLoadState=loaded\nUnitFileState=enabled")
    print("ActiveState=active\nSubState=running\nExecMainStatus=0")
    print("MainPID=" + str(state["pid"]))
    print("User=" + str(os.getuid()))
    print("FragmentPath=/etc/systemd/system/chaldea-waits.service\nDropInPaths=")
    print("PrivateUsers=yes\nNoNewPrivileges=yes\nProtectSystem=strict")
    print("ProtectHome=" + ("no" if state.get("bad_readiness") else "read-only"))
    print("ExecStart=" + command)
elif verb == "is-enabled":
    print("enabled")
elif verb == "is-active":
    print("active")
elif verb in ["start", "restart"]:
    if state.pop("fail_restart", False):
        print("injected restart failure", file=sys.stderr)
        rc = 1
    else:
        state["restarts"] += 1
        state["pid"] += 1
        state["loaded"] = json.loads(Path(os.environ["WAITS_RECOVERY_CONFIG"]).read_text())
state["calls"].append(verb)
state_path.write_text(json.dumps(state))
sys.exit(rc)
'''


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    safe(tmp_path)
    home = Path.home()
    for suffix in [".config/chaldea", ".local/state/chaldea", ".runtime"]:
        (home / suffix).mkdir(parents=True, exist_ok=True)
    unit = tmp_path / "system.service"
    state = tmp_path / "manager.json"
    state.write_text(json.dumps({"pid": 100, "restarts": 0, "loaded": {}, "calls": []}))
    executable = tmp_path / "fake-bin/systemctl"
    executable.parent.mkdir()
    executable.write_text(FAKE_MANAGER)
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent) + ":" + os.environ["PATH"])
    monkeypatch.setenv("WAITS_RECOVERY_STATE", str(state))
    monkeypatch.setenv("WAITS_RECOVERY_UNIT", str(unit))
    config = home / ".config/chaldea/waits.json"
    monkeypatch.setenv("WAITS_RECOVERY_CONFIG", str(config))
    listener = socket.socket(socket.AF_UNIX)
    endpoint = home / ".runtime/waits.sock"
    # AF_UNIX limits the bind name, even when the scratch directory is valid.
    with monkeypatch.context() as scratch:
        scratch.chdir(endpoint.parent)
        listener.bind(endpoint.name)
    endpoint.chmod(0o600)
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    variables = defaults | yaml.safe_load((ROLE / "vars/main.yml").read_text()) | {
        "fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid(), "user_gid": os.getgid()},
        "chaldea_node_version": "26.12.0",
        "chaldea_client_waits_resolved_runtime": str(home / ".local/share/chaldea/releases/fixture"),
        "chaldea_client_waits_environment": "fixture",
        "chaldea_client_waits_socket": str(endpoint),
    }

    def execute(port=7385, interrupt_after=None):
        selected = []
        canonical = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
        preflight = yaml.safe_load((ROLE / "tasks/waits-preflight.yml").read_text())
        names = {
            "Create only private waits directories",
            "Predict waits changes before writing definitions or configuration",
            "Persist waits restart intent before changing files",
            "Inspect durable waits restart intent",
            "Render waits configuration retaining the existing database and auth pointers",
            "Render the maintained policy loader startup check",
            "Install the system waits definition",
            "Start the sole system waits owner",
            "Wait for the private waits socket before reading readiness",
            "Inspect the private waits socket",
            "Require an owner-only socket before accepting readiness",
            "Read system readiness after starting",
            "Require the managed system service to be active under the fleet identity",
            "Clear waits restart intent only after successful verification",
        }
        for original in canonical:
            expanded = ([task for task in preflight if task["name"] in {
                            "Render the credential-free namespace checker", "Install the preflight in the system manager"}]
                        if original.get("ansible.builtin.import_tasks") == "waits-preflight.yml"
                        else [original] if original["name"] in names else [])
            for task in expanded:
                task = copy.deepcopy(task)
                task.pop("become", None)
                if "ansible.builtin.template" in task:
                    args = task["ansible.builtin.template"]
                    args["src"] = str(TEMPLATES) + "/" + args["src"]
                    if args.get("dest") in ["/etc/systemd/system/chaldea-waits.service",
                                            "/etc/systemd/system/chaldea-waits-preflight.service"]:
                        args["dest"] = str(unit if args["dest"].endswith("/chaldea-waits.service")
                                           else tmp_path / "preflight.service")
                        args.pop("owner", None)
                        args.pop("group", None)
                for item in task.get("loop", []):
                    if isinstance(item, dict) and item.get("dest") in [
                            "/etc/systemd/system/chaldea-waits.service",
                            "/etc/systemd/system/chaldea-waits-preflight.service"]:
                        item["dest"] = str(unit if item["dest"].endswith("/chaldea-waits.service")
                                           else tmp_path / "preflight.service")
                selected.append(task)
                if task["name"] == interrupt_after:
                    selected.append({"name": "Interrupt after the real file write",
                                     "ansible.builtin.fail": {"msg": "injected interruption"}})
                    break
            if selected and selected[-1]["name"] == "Interrupt after the real file write":
                break
        return play(tmp_path, variables | {"chaldea_client_waits_port": port}, selected)

    yield {"execute": execute, "state": state, "config": config,
           "marker": home / ".local/state/chaldea/waits-system-restart-required",
           "namespace": home / ".config/chaldea/waits-namespace-check.mjs"}
    listener.close()


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr


def read_state(recovery):
    return json.loads(recovery["state"].read_text())


def test_matching_files_resume_restarts_daemon_with_new_configuration(recovery):
    ok(recovery["execute"]())
    before = read_state(recovery)
    assert before["loaded"]["port"] == 7385
    interrupted = recovery["execute"](7386,
        "Render waits configuration retaining the existing database and auth pointers")
    assert interrupted.returncode != 0 and "injected interruption" in interrupted.stdout
    assert json.loads(recovery["config"].read_text())["port"] == 7386
    assert read_state(recovery)["loaded"]["port"] == 7385
    intent_persisted = recovery["marker"].exists()

    # All rendered files now match, but the active daemon still has old config.
    ok(recovery["execute"](7386))
    after = read_state(recovery)
    assert after["loaded"]["port"] == 7386, "active daemon retained stale configuration after resume"
    assert after["restarts"] == before["restarts"] + 1
    assert intent_persisted and not recovery["marker"].exists()
    ok(recovery["execute"](7386))
    assert read_state(recovery)["restarts"] == after["restarts"], "converged invocation restarted again"


@pytest.mark.parametrize("failure", ["fail_restart", "bad_readiness"])
def test_restart_or_readiness_failure_preserves_intent(recovery, failure):
    ok(recovery["execute"]())
    state = read_state(recovery)
    state[failure] = True
    recovery["state"].write_text(json.dumps(state))
    failed = recovery["execute"](7386)
    assert failed.returncode != 0
    assert recovery["marker"].exists()
    state = read_state(recovery)
    state[failure] = False
    recovery["state"].write_text(json.dumps(state))
    ok(recovery["execute"](7386))
    assert read_state(recovery)["loaded"]["port"] == 7386
    assert not recovery["marker"].exists()


def test_intent_precedes_preflight_checker_write_and_survives_resume(recovery):
    ok(recovery["execute"]())
    before = read_state(recovery)
    recovery["namespace"].write_text("// old checker bytes\n")
    interrupted = recovery["execute"](interrupt_after="Render the credential-free namespace checker")
    assert interrupted.returncode != 0 and "injected interruption" in interrupted.stdout
    assert recovery["marker"].exists(), "checker changed before restart intent was persisted"
    ok(recovery["execute"]())
    assert read_state(recovery)["restarts"] == before["restarts"] + 1
    assert not recovery["marker"].exists()
