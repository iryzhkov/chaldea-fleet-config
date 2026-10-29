"""Install real role tasks in scratch; verify pin failures, dry runs and file paths."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from host_artifact_fixture import PROGRAMS, stage

ROOT = Path(__file__).resolve().parents[1]


def run_role(base, variables, *, check=False, role="chaldea_host_artifact"):
    assert Path.home() != Path("/home/igor")
    assert base.is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    play = base / "install.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Isolated artifact installation", "hosts": "localhost",
        "connection": "local", "gather_facts": False,
        "vars": variables,
        "roles": [role],
    }]))
    environment = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    args = ["ansible-playbook", "-i", "localhost,", str(play)]
    if check:
        args += ["--check", "--diff"]
    return subprocess.run(args, env=environment, capture_output=True, text=True)


def test_install_checks_exact_payload_and_is_idempotent(tmp_path):
    pins = stage(tmp_path)
    first = run_role(tmp_path, pins)
    assert first.returncode == 0, first.stdout + first.stderr
    installed = tmp_path / "releases" / pins["chaldea_host_version"] / "host"
    for name in PROGRAMS:
        path = installed / name
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_uid == os.getuid()
    before = {str(p.relative_to(installed)): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    check = run_role(tmp_path, pins, check=True)
    assert check.returncode == 0, check.stdout + check.stderr
    assert "changed=0" in check.stdout
    second = run_role(tmp_path, pins)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "changed=0" in second.stdout, second.stdout + second.stderr
    assert before == {str(p.relative_to(installed)): p.read_bytes() for p in installed.rglob("*") if p.is_file()}


def test_fresh_check_without_cache_is_graceful_and_does_not_download(tmp_path):
    pins = stage(tmp_path)
    # No release cache and no network access required in a fresh dry run.
    pins["chaldea_host_artifact_archive_source"] = ""
    pins["chaldea_host_artifact_manifest_source"] = ""
    pins["chaldea_host_artifact_release_url"] = "https://invalid.invalid"
    result = run_role(tmp_path, pins, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Host release is not cached" in result.stdout
    assert not (tmp_path / "cache").exists()
    assert not (tmp_path / "releases").exists()


@pytest.mark.parametrize("failure", ["checksum", "manifest_version", "manifest_checksum"])
def test_pin_mismatch_is_rejected_before_install(tmp_path, failure):
    pins = stage(tmp_path)
    if failure == "checksum":
        pins["chaldea_host_sha256"] = "a" * 64
    else:
        manifest = Path(pins["chaldea_host_artifact_manifest_source"])
        data = json.loads(manifest.read_text())
        data["version" if failure == "manifest_version" else "sha256"] = "wrong"
        manifest.write_text(json.dumps(data))
    result = run_role(tmp_path, pins)
    assert result.returncode != 0
    assert not (tmp_path / "releases" / pins["chaldea_host_version"] / "host").exists()


def test_timer_roles_install_artifact_bytes_and_delivery_config(tmp_path, monkeypatch):
    pins = stage(tmp_path)
    home = tmp_path / "operator"
    state = tmp_path / "systemctl.json"
    state.write_text('{"units": {}, "calls": []}')
    monkeypatch.setenv("PATH", str(ROOT / "tests/fake-bin") + ":" + os.environ["PATH"])
    monkeypatch.setenv("FAKE_SYSTEMCTL_STATE", str(state))
    pins |= {"fleet_home": str(home), "retention_timer_enabled": False,
             "akasha_collector_enabled": False}
    result = run_role(tmp_path, pins, role="retention")
    assert result.returncode == 0, result.stdout + result.stderr
    source = tmp_path / "releases" / pins["chaldea_host_version"] / "host"
    for name, target in {
        "chaldea-retention": home / ".local/bin/chaldea-retention",
        "chaldea-timer-report": home / ".local/bin/chaldea-timer-report",
        "chaldea_outcome.py": home / ".local/share/chaldea/timer-reporting/chaldea_outcome.py",
    }.items():
        assert target.read_bytes() == (source / name).read_bytes()
        assert target.stat().st_uid == os.getuid()
    config = home / ".config/chaldea/timer-reporting.json"
    assert json.loads(config.read_text()) == {"delivery": "feed"}
    # Keep the collector disabled while exercising queue configuration directly.
    reporting = yaml.safe_load((ROOT / "roles/timer_reporting/tasks/main.yml").read_text())
    delivery = next(t for t in reporting if t["name"] == "Configure timer outcome delivery")
    from jinja2 import Environment
    from ansible.plugins.filter.core import FilterModule
    env = Environment()
    env.filters.update(FilterModule().filters())
    env.filters["bool"] = bool
    assert json.loads(env.from_string(delivery["ansible.builtin.copy"]["content"]).render(
        akasha_collector_enabled=True)) == {"delivery": "queue"}


def test_role_program_paths_and_access_contract_are_canonical():
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    assert inventory["chaldea_access_paths"] == {
        "root": "/etc/chaldea-access-trust",
        "state": "/var/lib/chaldea-access-trust",
        "public": "/var/lib/chaldea-access-trust-public",
        "run": "/run/chaldea-access-trust",
        "bundle": "/var/lib/chaldea-access-trust-public/bundle.jws",
        "clock_health": "/run/chaldea-access-trust/clock-health.json",
        "updater_state": "/var/lib/chaldea-access-trust/updater.sqlite",
        "verifier_state": "/var/lib/akasha/access-state.db",
    }
    for role in ("chaldea_job_host", "retention", "timer_reporting",
                 "akasha_collector", "chaldea_access_trust"):
        tasks = yaml.safe_load((ROOT / "roles" / role / "tasks/main.yml").read_text())
        assert tasks[0]["ansible.builtin.include_role"]["name"] == "chaldea_host_artifact"
    job = yaml.safe_load((ROOT / "roles/chaldea_job_host/tasks/main.yml").read_text())
    protocol = next(t["ansible.builtin.copy"] for t in job if t["name"] == "Install the server's protocol definition alongside the server")
    assert protocol["src"] == "{{ chaldea_host_artifact_root }}/exec-protocol.json"
    assert protocol["dest"] == "{{ chaldea_job_host_server | dirname }}/exec-protocol.json"
    assert next(i for i, t in enumerate(job) if t["name"] == "Install the server\'s protocol definition alongside the server") < next(i for i, t in enumerate(job) if t["name"] == "Install the self-contained protocol version one server")
    assert protocol["owner"] == "root" and protocol["mode"] == "0644"

def test_actual_program_copy_tasks_install_and_dry_diff_in_scratch(tmp_path):
    """Use the production copy tasks; redirect only destination, privilege and uid."""
    import copy
    pins = stage(tmp_path)
    home = tmp_path / "operator"
    rootfs = tmp_path / "rootfs"
    pins |= {
        "fleet_home": str(home),
        "retention_script": str(home / ".local/bin/chaldea-retention"),
        "chaldea_job_host_server": str(rootfs / "usr/local/libexec/chaldea-job-server"),
        "chaldea_access_trust_fetcher": str(rootfs / "usr/local/libexec/chaldea-access-trust-fetch"),
    }
    selections = {
        "chaldea_job_host/tasks/main.yml": [
            "Install the image creation command", "Install the self-contained protocol version one server",
            "Install the server's protocol definition alongside the server",
        ],
        "chaldea_job_host/tasks/toolchains.yml": ["Install the verified toolchain manager"],
        "chaldea_access_trust/tasks/main.yml": ["Install byte-only Git downloader"],
        "retention/tasks/main.yml": ["Install the retention script"],
        "timer_reporting/tasks/main.yml": ["Install the timer outcome wrapper", "Install the safe Ansible callback"],
    }
    # Source name -> canonical production destination and mode.
    expected = {
        "chaldea-job-image": ("/usr/local/libexec/chaldea-job-image", "0755"),
        "chaldea-job-server": ("{{ chaldea_job_host_server }}", "0755"),
        "exec-protocol.json": ("{{ chaldea_job_host_server | dirname }}/exec-protocol.json", "0644"),
        "chaldea-job-toolchains": ("/usr/local/libexec/chaldea-job-toolchains", "0755"),
        "chaldea-access-trust-fetch": ("{{ chaldea_access_trust_fetcher }}", "0755"),
        "chaldea-retention": ("{{ retention_script }}", "0755"),
        "chaldea-timer-report": ("{{ fleet_home }}/.local/bin/chaldea-timer-report", "0755"),
        "chaldea_outcome.py": ("{{ fleet_home }}/.local/share/chaldea/timer-reporting/chaldea_outcome.py", "0644"),
    }
    copied = []
    for path, names in selections.items():
        tasks = yaml.safe_load((ROOT / "roles" / path).read_text())
        for name in names:
            task = copy.deepcopy(next(t for t in tasks if t["name"] == name))
            spec = task["ansible.builtin.copy"]
            source = spec["src"].split("/")[-1]
            dest, mode = expected[source]
            assert spec["dest"] == dest and spec["mode"] == mode
            assert spec["remote_src"] is True
            assert spec["src"] == "{{ chaldea_host_artifact_root }}/" + source
            assert spec["owner"] in ("root", "{{ chaldea_host_artifact_owner }}")
            assert spec["group"] in ("root", "{{ chaldea_host_artifact_group }}")
            if dest.startswith("/"):
                spec["dest"] = str(rootfs) + dest
            task["become"] = False
            spec["owner"], spec["group"] = str(os.getuid()), str(os.getgid())
            copied.append(task)
    play = tmp_path / "copies.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Actual copy tasks with isolated destinations", "hosts": "localhost",
        "connection": "local", "gather_facts": False, "vars": pins,
        "tasks": [
            {"name": "Prepare fixture destination directories", "ansible.builtin.file": {
                "path": "{{ item }}", "state": "directory", "mode": "0755"},
             "loop": [str(rootfs / "usr/local/bin"), str(rootfs / "usr/local/libexec"),
                      str(home / ".local/bin"), str(home / ".local/share/chaldea/timer-reporting")]},
            {"name": "Install artifact", "ansible.builtin.include_role": {
                "name": "chaldea_host_artifact", "public": True}},
            *copied,
        ],
    }]))
    environment = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    command = ["ansible-playbook", "-i", "localhost,", str(play)]
    first = subprocess.run(command, env=environment, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    artifact = tmp_path / "releases" / pins["chaldea_host_version"] / "host"
    targets = {}
    for source, (dest, mode) in expected.items():
        if source == "exec-protocol.json":
            target = Path(pins["chaldea_job_host_server"]).with_name("exec-protocol.json")
        elif dest.startswith("/"):
            target = rootfs / dest.lstrip("/")
        elif "chaldea_job_host_server" in dest:
            target = Path(pins["chaldea_job_host_server"])
        elif "chaldea_access_trust_fetcher" in dest:
            target = Path(pins["chaldea_access_trust_fetcher"])
        elif "retention_script" in dest:
            target = Path(pins["retention_script"])
        else:
            target = Path(dest.replace("{{ fleet_home }}", str(home)))
        expected_source = artifact / source
        assert target.read_bytes() == expected_source.read_bytes()
        assert target.stat().st_mode & 0o777 == int(mode, 8)
        assert target.stat().st_uid == os.getuid()
        targets[source] = target
    clean = subprocess.run(command + ["--check", "--diff"], env=environment, capture_output=True, text=True)
    assert clean.returncode == 0 and "changed=0" in clean.stdout, clean.stdout + clean.stderr
    target = targets["chaldea-job-server"]
    target.write_text("# drifted installed server\n")
    drift = subprocess.run(command + ["--check", "--diff"], env=environment, capture_output=True, text=True)
    assert drift.returncode == 0, drift.stdout + drift.stderr
    assert "changed=1" in drift.stdout
    assert "TASK [Install the self-contained protocol version one server]" in drift.stdout
    assert target.read_text() == "# drifted installed server\n"
    evidence_path = os.environ.get("CHALDEA_HOST_TEST_EVIDENCE")
    if evidence_path:
        import hashlib
        evidence = Path(evidence_path).resolve()
        assert evidence.is_relative_to(Path(os.environ["TMPDIR"]).resolve())
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "clean-check.log").write_text(clean.stdout + clean.stderr)
        (evidence / "drift-check.log").write_text(drift.stdout + drift.stderr)
        (evidence / "files.json").write_text(json.dumps({
            "kind": "candidate" if os.environ.get("CHALDEA_HOST_TEST_ARCHIVE") else "synthetic",
            "version": pins["chaldea_host_version"], "archive_sha256": pins["chaldea_host_sha256"],
            "release_payload": [{
                "source": name, "mode": format((artifact / name).stat().st_mode & 0o777, "04o"),
                "effective_test_uid": (artifact / name).stat().st_uid,
                "effective_test_gid": (artifact / name).stat().st_gid,
                "sha256": hashlib.sha256((artifact / name).read_bytes()).hexdigest(),
            } for name in PROGRAMS],
            "files": [{
                "source": source, "production_destination": dest,
                "mode": mode, "production_owner": "root", "production_group": "root",
                "effective_test_uid": os.getuid(), "effective_test_gid": os.getgid(),
                "source_kind": "artifact",
                "source_file_sha256": hashlib.sha256((artifact / source).read_bytes()).hexdigest(),
                "installed_bytes_matched": True,
            } for source, (dest, mode) in expected.items()],
        }, indent=2))

def test_retention_keeps_configured_and_one_prior_release_and_cache(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/chaldea_host_artifact/defaults/main.yml").read_text())
    assert defaults["chaldea_host_artifact_preserve_versions"] == []
    pins = stage(tmp_path)
    root = Path(pins["chaldea_host_artifact_release_root"])
    cache = Path(pins["chaldea_host_artifact_cache"])
    cache.mkdir()
    for version, timestamp in (("host-v9.0.1", 10), ("host-v9.0.2", 20)):
        path = root / version
        path.mkdir(parents=True)
        (path / "sentinel").write_text(version)
        os.utime(path, (timestamp, timestamp))
        for extension in (".tar.gz", ".json"):
            (cache / (version + extension)).write_text("old cache")
    (cache / "host-v9.0.3.tar.gz").write_text("orphaned download")
    (cache / "operator-note").write_text("preserve unrelated files")
    result = run_role(tmp_path, pins)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(path.name for path in root.iterdir()) == sorted([pins["chaldea_host_version"], "host-v9.0.2"])
    assert sorted(path.name for path in cache.iterdir()) == sorted([
        pins["chaldea_host_version"] + ".tar.gz", pins["chaldea_host_version"] + ".json",
        "host-v9.0.2.tar.gz", "host-v9.0.2.json", "operator-note",
    ])


@pytest.mark.parametrize("extra", [False, True])
def test_retention_keeps_all_nine_or_ten_through_runtime_then_shared_calls(tmp_path, extra):
    pins = stage(tmp_path)
    root = Path(pins["chaldea_host_artifact_release_root"])
    cache = Path(pins["chaldea_host_artifact_cache"])
    root.mkdir()
    cache.mkdir()
    older = [f"host-v0.2.{i}" for i in (2, 3, 4, 6, 7, 8, 9, 10)]
    if extra:
        older.append("host-v0.2.14")
    runtime = "host-v0.2.15" if extra else "host-v0.2.11"
    archive = Path(pins["chaldea_host_artifact_archive_source"]).read_bytes()
    original_cache = {}
    for index, version in enumerate(older):
        release = root / version
        release.mkdir()
        (release / "consumer").write_text(version)
        os.utime(release, (index + 1, index + 1))
        for suffix, content in (
            (".tar.gz", archive),
            (".json", json.dumps({"version": version, "sha256": pins["chaldea_host_sha256"]}).encode()),
        ):
            name = version + suffix
            (cache / name).write_bytes(content)
            original_cache[name] = content
    calls = (
        (runtime, older[:-1]),  # newest prior plus seven or eight explicit old releases
        ("host-v0.2.2", older[1:]),   # newest runtime plus the remaining old releases
    )
    for selected, preserved in calls:
        pins["chaldea_host_version"] = selected
        pins["chaldea_host_artifact_preserve_versions"] = preserved
        Path(pins["chaldea_host_artifact_manifest_source"]).write_text(
            json.dumps({"version": selected, "sha256": pins["chaldea_host_sha256"]}))
        result = run_role(tmp_path, pins)
        assert result.returncode == 0, result.stdout + result.stderr
        assert {p.name for p in root.iterdir()} == set(older) | {runtime}
        assert {p.name for p in cache.iterdir()} == {
            version + suffix for version in [*older, runtime] for suffix in (".tar.gz", ".json")
        }
        for version in older:
            assert (root / version / "consumer").read_text() == version
        for name, content in original_cache.items():
            assert (cache / name).read_bytes() == content
        # Fixture ordering only. Real target mtimes remain an operator gate.
        os.utime(root / runtime, (100, 100))
        again = run_role(tmp_path, pins)
        assert again.returncode == 0 and "changed=0" in again.stdout, again.stdout + again.stderr
        assert {p.name for p in root.iterdir()} == set(older) | {runtime}
