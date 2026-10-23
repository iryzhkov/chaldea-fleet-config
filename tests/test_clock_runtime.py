"""Exercise the production shared/clock artifact sequence without host services."""
import copy
import json
import os
from pathlib import Path
import subprocess

import yaml
from host_artifact_fixture import stage

ROOT = Path(__file__).resolve().parents[1]


def test_clock_install_is_independent_and_retains_both_consumers(tmp_path):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    pins = stage(tmp_path / "shared")
    clock = stage(tmp_path / "clock")
    version = "host-v0.0.1-clock"
    manifest = Path(clock["chaldea_host_artifact_manifest_source"])
    data = json.loads(manifest.read_text())
    data["version"] = version
    manifest.write_text(json.dumps(data))
    pins |= {
        "chaldea_clock_host_version": version,
        "chaldea_clock_host_sha256": clock["chaldea_host_sha256"],
        "chaldea_host_artifact_preserve_versions": ["host-v0.2.2"],
    }
    prior = Path(pins["chaldea_host_artifact_release_root"]) / "host-v0.2.2"
    prior.mkdir(parents=True)
    (prior / "consumer").write_text("unchanged")
    tasks = copy.deepcopy(yaml.safe_load(
        (ROOT / "roles/chaldea_access_trust/tasks/main.yml").read_text())[:2])
    tasks[1]["vars"] |= {
        "chaldea_host_artifact_release_root": clock["chaldea_host_artifact_release_root"],
        "chaldea_host_artifact_cache": clock["chaldea_host_artifact_cache"],
        "chaldea_host_artifact_archive_source": clock["chaldea_host_artifact_archive_source"],
        "chaldea_host_artifact_manifest_source": clock["chaldea_host_artifact_manifest_source"],
    }
    tasks.append({"name": "Shared consumer pin is unchanged", "ansible.builtin.assert": {
        "that": ["chaldea_host_version == '" + pins["chaldea_host_version"] + "'"]}})
    play = tmp_path / "install.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": pins, "tasks": tasks,
    }]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    for attempt in range(2):
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        if attempt:
            assert "changed=0" in result.stdout, result.stdout
    assert (prior.parent / pins["chaldea_host_version"] / "host/access-maintenance.mjs").is_file()
    assert (Path(clock["chaldea_host_artifact_release_root"]) / version / "host/access-maintenance.mjs").is_file()
    assert (prior / "consumer").read_text() == "unchanged"
