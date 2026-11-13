"""Exercise the real collector/artifact roles without touching a host user manager."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import yaml
import pytest
from host_artifact_fixture import stage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("homelab_retention", [False, True])
def test_collector_installs_independently_and_preserves_every_shared_asset(tmp_path, homelab_retention):
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
    retained = {}
    if homelab_retention:
        inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
        homelab = inventory["all"]["children"]["servers"]["hosts"]["homelab"]
        keep = homelab["akasha_collector_preserve_versions"]
        # The server's active 022 and rollback 020 share this root with the collector.
        assert keep == ["host-v0.2.17", "host-v0.2.18", "host-v0.2.20", "host-v0.2.22"]
        variables["akasha_collector_preserve_versions"] = keep
        release_root = Path(variables["akasha_collector_release_root"])
        cache = Path(variables["akasha_collector_cache"])
        release_root.mkdir(); cache.mkdir()
        for index, version in enumerate(keep, 1):
            release = release_root / version
            release.mkdir()
            (release / "sentinel").write_text(version)
            os.utime(release, (index, index))
            paths = [release, release / "sentinel"]
            for suffix in (".tar.gz", ".json"):
                entry = cache / (version + suffix)
                entry.write_text(version)
                paths.append(entry)
            for path in paths:
                stat = path.stat()
                retained[path] = (path.read_bytes() if path.is_file() else None,
                                  stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_mode)
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
        if homelab_retention:
            assert sorted(p.name for p in release_root.iterdir()) == sorted(
                keep + [pins["chaldea_host_version"]])
        for path, expected in retained.items():
            stat = path.stat()
            assert (path.read_bytes() if path.is_file() else None,
                    stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_mode) == expected
    assert Path(variables["akasha_collector_script"]).is_file()
    unit = (tmp_path / "collector.service").read_text()
    assert str(shared) not in unit
    assert variables["akasha_collector_script"] in unit
