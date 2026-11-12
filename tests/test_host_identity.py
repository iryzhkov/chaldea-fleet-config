"""Host credential selection; native configuration stays at the main golden bytes."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/webmcp_interactive/tasks"


def test_native_adapters_match_main_golden():
    # Git blob IDs at 72add22. Jobs omit .git, so check the golden bytes directly.
    for path, expected in {
        "roles/mcp_registrations/library/mcp_registration.py": "bce2f2f5e13d7fa4347ebcca55d81850c6d15903",
        "roles/mcp_registrations/tasks/main.yml": "24d236dcde610c545ffd16c860a1ec0986973f97",
        "roles/webmcp_interactive/templates/opencode-webmcp-jocasta.js.j2": "70f98a89a833cc61e43733ac4b8096096e4215b2",
    }.items():
        data = (ROOT / path).read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == expected


@pytest.mark.parametrize("host", ["laptop", "omarchy-pc", "agent-a", "agent-b"])
@pytest.mark.parametrize("enabled", [False, True])
def test_rendered_credentials_and_missing_file_refusal(tmp_path, host, enabled):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    main = yaml.safe_load((TASKS / "main.yml").read_text())
    writer = yaml.safe_load((TASKS / "holonet-writer.yml").read_text())
    credentials = []
    for task in main + writer:
        for value in task.get("loop", []):
            if isinstance(value, str) and ".app-password" in value:
                credentials.append(value)
    assert len(credentials) == 5
    play_tasks = []
    for value, profile in zip(credentials, ["ov-interactive-codex", "ov-full-interactive",
                                           "shizune-interactive", "holonet-interactive",
                                           "holonet-recommendations"]):
        play_tasks += [
            {"name": "Render credential", "ansible.builtin.set_fact": {"rendered": value}},
            {"name": "Compare selected credential", "ansible.builtin.assert": {"that": [
                "rendered == expected"]}, "vars": {"expected":
                    str(tmp_path / ".config/chaldea/authentik") + "/" +
                    ("host" if enabled else profile) + ".app-password"}},
        ]
    custody = yaml.safe_load((TASKS / "host-identity.yml").read_text())[:2]
    # The actual role tasks must refuse missing host credentials when selected.
    play_tasks += custody
    play = tmp_path / "proof.yml"
    play.write_text(yaml.safe_dump([{"hosts": host, "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(tmp_path), "chaldea_host_identity_enabled": enabled,
                 "ansible_facts": {"user_uid": os.getuid()}}, "tasks": play_tasks}]))
    result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)],
                            capture_output=True, text=True)
    if enabled:
        assert result.returncode != 0
        assert "host.app-password is missing or unsafe" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
