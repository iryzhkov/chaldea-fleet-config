"""Capture configuration uses the existing private token metadata only."""
import json
from pathlib import Path

import yaml

from test_mission_control import fixture_role, play, ok


def test_capture_real_configuration_cold_check_idempotence_and_token_denial(tmp_path):
    role = fixture_role(tmp_path, "mission_control_capture")
    token = Path.home() / ".config/chaldea/t3-token"
    token.parent.mkdir(parents=True)
    token.write_text("public-fixture-token")
    token.chmod(0o600)
    snapshot = Path.home() / ".local/state/chaldea/mission-control/latest.json"
    values = dict(mission_control_capture_enabled=True, mission_control_runtime_enabled=True,
        mission_control_runtime_node="/bin/true", mission_control_runtime_release_root=str(tmp_path / "runtime"),
        mission_control_runtime_version="client-v9.8.7", mission_control_capture_t3_base_dir="/fixture/t3")
    ok(play(tmp_path, "agent-a", roles=[role], values=values, check=True))
    source = Path(role) / "tasks/main.yml"
    tasks = yaml.safe_load(source.read_text())
    tasks[0]["block"] = [row for row in tasks[0]["block"] if "ansible.builtin.fail" not in row]
    source.write_text(yaml.safe_dump(tasks))
    ok(play(tmp_path, "agent-a", roles=[role], values=values))
    path = Path.home() / ".config/chaldea/mission-control-capture.json"
    assert json.loads(path.read_text()) == dict(host="agent-a", t3BaseDir="/fixture/t3",
        tokenFile=str(token), snapshotFile=str(snapshot), tokenSemanticsQualified=False)
    assert path.stat().st_mode & 0o777 == 0o600
    assert token.read_text() == "public-fixture-token"
    again = play(tmp_path, "agent-a", roles=[role], values=values)
    ok(again)
    assert "changed=0" in again.stdout
    before = path.read_bytes()
    token.chmod(0o644)
    refused = play(tmp_path, "agent-a", roles=[role], values=values)
    assert refused.returncode != 0
    assert "Require an existing private igor read token" in refused.stdout
    assert path.read_bytes() == before
    foreign = play(tmp_path, "other", roles=[role], values=values)
    assert foreign.returncode != 0
    assert "Require the exact capture host" in foreign.stdout
