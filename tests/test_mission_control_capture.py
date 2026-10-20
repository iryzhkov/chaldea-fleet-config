"""Capture configuration uses the existing private token metadata only."""
import json
from pathlib import Path

import yaml
import pytest

from test_mission_control import fixture_role, play, ok


@pytest.mark.parametrize("interruption", ["download", "manager", "process"])
def test_capture_interrupted_update_recovery_at_real_callsite(tmp_path, monkeypatch, interruption):
    """Run the shipped composition with disposable files and manager boundaries."""
    import http.server
    import os
    import subprocess
    import threading
    from client_artifact_fixture import stage
    from test_mission_control import ROOT, instrument_activation

    capture = fixture_role(tmp_path, "mission_control_capture")
    runtime = fixture_role(tmp_path, "mission_control_runtime")
    instrument_activation(capture, tmp_path)
    artifact = stage(tmp_path / "artifact")
    token = Path.home() / ".config/chaldea/t3-token"
    token.parent.mkdir(parents=True)
    token.write_text("public-fixture-token")
    token.chmod(0o600)
    values = dict(mission_control_capture_enabled=True, mission_control_runtime_enabled=True,
        mission_control_activate=True, mission_control_capture_laptop_qualified=True,
        mission_control_runtime_node=str(tmp_path / "node/bin/node"),
        mission_control_runtime_release_root=str(tmp_path / "runtime"),
        mission_control_runtime_version=artifact["chaldea_client_version"],
        mission_control_runtime_sha256=artifact["chaldea_client_sha256"],
        mission_control_runtime_archive_source=artifact["chaldea_client_archive_source"],
        mission_control_runtime_manifest_source=artifact["chaldea_client_manifest_source"])

    binary = tmp_path / "bin/systemd-analyze"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary.parent) + ":" + os.environ["PATH"])

    # Establish the old disk unit and active process through the real capture role.
    tasks = [{"ansible.builtin.include_role": dict(name=capture)},
             {"ansible.builtin.include_role": dict(name=capture, tasks_from="activate")}]
    ok(play(tmp_path, "laptop", tasks=tasks,
            values=values | dict(mission_control_runtime_version="client-v0.4.9")))
    unit = tmp_path / "units/mission-control-capture.service"
    old = unit.read_bytes()
    manager = tmp_path / "manager.json"
    prior = manager.read_bytes()
    if interruption != "download":
        # A prior invocation wrote the new unit but never activated it.
        ok(play(tmp_path, "laptop", roles=[capture], values=values))
        if interruption == "process":
            # An unrelated daemon-reload loaded the new unit without restarting.
            state = json.loads(manager.read_text())
            state["_loaded"] = next(x.removeprefix("ExecStart=") for x in unit.read_text().splitlines()
                                    if x.startswith("ExecStart="))
            manager.write_text(json.dumps(state))

    # Relocate role names only in the shipped playbook, keeping role order and gates.
    composition = yaml.safe_load((ROOT / "playbooks/mission-control.yml").read_text())
    row = composition[0]
    row["become"] = False
    row["vars"] = values
    mapping = dict(mission_control_capture=capture, mission_control_runtime=runtime)
    row["roles"] = [mapping[name] for name in row["roles"]]
    for task in row["tasks"]:
        task["ansible.builtin.include_role"]["name"] = capture

    class FailedManifest(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_error(503, "injected manifest download failure")
        def log_message(self, format, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FailedManifest)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        if interruption == "download":
            # Archive is supplied; the real get_url fails on the missing manifest.
            row["vars"] = values | dict(mission_control_runtime_manifest_source="")
            source = Path(runtime) / "tasks/main.yml"
            source.write_text(source.read_text().replace(
                "https://github.com/iryzhkov/chaldea/releases/download/",
                f"http://127.0.0.1:{server.server_port}/"))
        source = tmp_path / "composition.yml"
        source.write_text(yaml.safe_dump(composition))
        def run():
            return subprocess.run(["ansible-playbook", "-i", "laptop,", "--limit", "laptop", str(source)],
                env=dict(os.environ, ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible-local"),
                         ANSIBLE_REMOTE_TEMP=str(tmp_path / "ansible-remote"),
                         ANSIBLE_LIBRARY=str(ROOT / "library")),
                text=True, capture_output=True)
        if interruption == "download":
            failed = run()
            assert failed.returncode != 0 and "503" in failed.stdout, failed.stdout + failed.stderr
            assert manager.read_bytes() == prior
            assert unit.read_bytes() == old, "failed runtime download mutated the capture unit"
            row["vars"] = values
            source.write_text(yaml.safe_dump(composition))
        result = run()
        ok(result)
        state = json.loads(manager.read_text())
        assert f"/{values['mission_control_runtime_version']}/bin/chaldea" in state["_running"], (
            "retry kept the old running capture", state, result.stdout)
        assert state["_running"] == state["_loaded"]
        assert (tmp_path / "runtime/releases" / values["mission_control_runtime_version"] / "bin/chaldea").is_file()
        again = run()
        ok(again)
        assert "changed=0" in again.stdout, again.stdout
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("host", ["agent-a", "omarchy-pc", "agent-b", "laptop"])
def test_capture_real_configuration_cold_check_idempotence_and_token_denial(tmp_path, host):
    role = fixture_role(tmp_path, "mission_control_capture")
    token = Path.home() / ".config/chaldea/t3-token"
    token.parent.mkdir(parents=True)
    token.write_text("public-fixture-token")
    token.chmod(0o600)
    snapshot = Path.home() / ".local/state/chaldea/mission-control/latest.json"
    values = dict(mission_control_capture_enabled=True, mission_control_runtime_enabled=True,
        mission_control_runtime_node="/bin/true", mission_control_runtime_release_root=str(tmp_path / "runtime"),
        mission_control_runtime_version="client-v9.8.7", mission_control_capture_laptop_qualified=True,
        mission_control_capture_t3_base_dir="/fixture/t3")
    if host == "laptop":
        denied = play(tmp_path, host, roles=[role], values=values | dict(mission_control_capture_laptop_qualified=False))
        assert denied.returncode != 0 and "Require the exact capture host" in denied.stdout
        denied = play(tmp_path, host, roles=[role], values=values | dict(mission_control_capture_host="laptop"))
        assert denied.returncode != 0 and "Require the exact capture host" in denied.stdout
    ok(play(tmp_path, host, roles=[role], values=values, check=True))
    source = Path(role) / "tasks/main.yml"
    tasks = yaml.safe_load(source.read_text())
    tasks[0]["block"] = [row for row in tasks[0]["block"] if "ansible.builtin.fail" not in row]
    source.write_text(yaml.safe_dump(tasks))
    ok(play(tmp_path, host, roles=[role], values=values))
    path = Path.home() / ".config/chaldea/mission-control-capture.json"
    assert json.loads(path.read_text()) == dict(host="omarchy-macbook-air-igor" if host == "laptop" else host, t3BaseDir="/fixture/t3",
        tokenFile=str(token), snapshotFile=str(snapshot), tokenSemanticsQualified=False)
    assert path.stat().st_mode & 0o777 == 0o600
    assert token.read_text() == "public-fixture-token"
    again = play(tmp_path, host, roles=[role], values=values)
    ok(again)
    assert "changed=0" in again.stdout
    before = path.read_bytes()
    token.chmod(0o644)
    refused = play(tmp_path, host, roles=[role], values=values)
    assert refused.returncode != 0
    assert "Require an existing private igor read token" in refused.stdout
    assert path.read_bytes() == before
    checked = play(tmp_path, host, roles=[role], values=values, check=True)
    assert checked.returncode != 0 and "Require an existing private igor read token" in checked.stdout
    assert path.read_bytes() == before
    foreign = play(tmp_path, "other", roles=[role], values=values)
    assert foreign.returncode != 0
    assert "Require the exact capture host" in foreign.stdout



@pytest.mark.parametrize("host", ["agent-a", "omarchy-pc", "agent-b", "laptop"])
def test_capture_system_gate_failure_and_warm_restart(tmp_path, host):
    import os
    import sys
    from test_mission_control import instrument_activation
    role = fixture_role(tmp_path, "mission_control_capture")
    instrument_activation(role, tmp_path)
    token = Path.home() / ".config/chaldea/t3-token"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text("public-fixture-token")
    token.chmod(0o600)
    binary = tmp_path / "bin/systemd-analyze"
    binary.parent.mkdir()
    binary.write_text("#!" + sys.executable + "\n" + """import json, os, pathlib, sys
p = pathlib.Path(os.environ['FIXTURE_VERIFY_LOG'])
with p.open('a') as out:
    out.write(json.dumps(sys.argv[1:]) + '\\n')
assert sys.argv[1:3] == ['verify', '--man=no']
assert len(sys.argv) == 4 and sys.argv[3].endswith('/mission-control-capture.service')
assert pathlib.Path(sys.argv[3]).is_file()
sys.exit(1 if os.environ.get('FIXTURE_VERIFY_FAIL') else 0)
""")
    binary.chmod(0o755)
    old_path = os.environ["PATH"]
    os.environ["PATH"] = str(binary.parent) + ":" + old_path
    os.environ["FIXTURE_VERIFY_LOG"] = str(tmp_path / "verify.events")
    values = dict(mission_control_capture_enabled=True, mission_control_runtime_enabled=True,
        mission_control_runtime_node="/bin/true", mission_control_runtime_release_root="/fixture",
        mission_control_runtime_version="client-v9.8.7", mission_control_capture_laptop_qualified=True)
    tasks = [{"ansible.builtin.include_role": dict(name=role)},
             {"ansible.builtin.include_role": dict(name=role, tasks_from="activate")}]
    try:
        refused = play(tmp_path, host, roles=[role], values=values | dict(
            fixture_services={"mission-control-capture.service": dict(state="running", status="enabled")}))
        assert refused.returncode != 0 and not (tmp_path / "manager.json").exists()
        ok(play(tmp_path, host, roles=[role], values=values))
        assert not (tmp_path / "manager.json").exists()
        values["mission_control_activate"] = True
        os.environ["FIXTURE_VERIFY_FAIL"] = "1"
        failed = play(tmp_path, host, tasks=tasks, values=values)
        assert failed.returncode != 0 and not (tmp_path / "manager.json").exists()
        del os.environ["FIXTURE_VERIFY_FAIL"]
        ok(play(tmp_path, host, tasks=tasks, values=values))
        config = Path.home() / ".config/chaldea/mission-control-capture.json"
        config.write_text("{}")
        unit = tmp_path / "units/mission-control-capture.service"
        unit.write_text("[Service]\n")
        protected = [config, unit, tmp_path / "manager.json", tmp_path / "manager.events", tmp_path / "verify.events"]
        before = [(p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in protected]
        checked = play(tmp_path, host, tasks=tasks, values=values, check=True)
        ok(checked)
        assert "t3BaseDir" in checked.stdout and "NoNewPrivileges=yes" in checked.stdout
        assert "after:" in checked.stdout and "changed=0" not in checked.stdout
        assert before == [(p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in protected]
        foreign = play(tmp_path, "other", roles=[role], values=values, check=True)
        assert foreign.returncode != 0 and "Require the exact capture host" in foreign.stdout
        ok(play(tmp_path, host, tasks=tasks, values=values))
        events = [json.loads(line) for line in (tmp_path / "manager.events").read_text().splitlines()]
        assert events[-1]["state"] == "restarted"
        again = play(tmp_path, host, tasks=tasks, values=values)
        ok(again)
        assert "changed=0" in again.stdout
    finally:
        os.environ["PATH"] = old_path
        os.environ.pop("FIXTURE_VERIFY_FAIL", None)
        os.environ.pop("FIXTURE_VERIFY_LOG", None)
