"""Exercise the real collector/artifact roles without touching a host user manager."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import yaml
from host_artifact_fixture import stage

ROOT = Path(__file__).resolve().parents[1]


def test_collector_installs_independently_and_preserves_every_shared_asset(tmp_path):
    pins = stage(tmp_path)
    shared = tmp_path / "shared"
    shared.mkdir()
    for i in range(10):
        (shared / f"old-{i}").write_text(f"rollback-{i}")
    def snapshot():
        return {p.name: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns,
                         p.stat().st_ctime_ns, p.stat().st_mode)
                for p in shared.iterdir()}
    before = snapshot()
    roles = tmp_path / "roles"
    for name in ("chaldea_host_artifact", "akasha_collector"):
        shutil.copytree(ROOT / "roles" / name, roles / name)
    target = roles / "user_timer" / "tasks"
    target.mkdir(parents=True)
    (target / "main.yml").write_text(yaml.safe_dump([
        {"ansible.builtin.assert": {"that": [
            "'flock --nonblock' in user_timer_service",
            "akasha_collector_script in user_timer_service",
            "'AKASHA_' not in user_timer_service",
        ]}},
        {"ansible.builtin.copy": {"content": "{{ user_timer_service }}",
                                  "dest": str(tmp_path / "collector.service"), "mode": "0600"}},
    ]))
    variables = {**pins, "fleet_home": str(tmp_path / "producer"),
                 "chaldea_host_version": "host-v0.2.2",
                 "chaldea_host_artifact_release_root": str(shared),
                 "chaldea_host_artifact_cache": str(shared),
                 "akasha_collector_version": pins["chaldea_host_version"],
                 "akasha_collector_sha256": pins["chaldea_host_sha256"],
                 "akasha_collector_release_root": str(tmp_path / "independent"),
                 "akasha_collector_cache": str(tmp_path / "independent-cache"),
                 "akasha_collector_script": str(tmp_path / "independent" / pins["chaldea_host_version"] / "host/akasha-collector.mjs"),
                 "akasha_collector_enabled": True,
                 "akasha_collector_url": "https://akasha.example",
                 "akasha_collector_token_helper": "/approved/helper",
                 "akasha_collector_node": "/approved/node"}
    play = tmp_path / "scope.yml"
    play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local",
                                    "gather_facts": False, "vars": variables,
                                    "roles": ["akasha_collector"]}]))
    env = {**os.environ, "ANSIBLE_ROLES_PATH": str(roles)}
    for attempt in range(2):
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        if attempt:
            assert "changed=0" in result.stdout
        assert snapshot() == before
    assert Path(variables["akasha_collector_script"]).is_file()
    unit = (tmp_path / "collector.service").read_text()
    assert str(shared) not in unit
    assert variables["akasha_collector_script"] in unit
