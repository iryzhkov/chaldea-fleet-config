"""Apply the real client role only in scratch homes, behind a fake user manager."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def safe(base):
    scratch = Path(os.environ["TMPDIR"]).resolve()
    assert scratch != Path("/tmp") and not scratch.is_relative_to("/tmp")
    assert base.resolve().is_relative_to(scratch)
    assert Path.home().is_relative_to(scratch), "test HOME must be scratch before any write"
    assert Path.home() != Path("/home/igor")


def fixture(base, monkeypatch, version="client-v9.0.0"):
    safe(base)
    home = Path.home()
    assert home.is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    files = {"bin/chaldea": b"#!/usr/bin/env node\n", "src/cli.ts": b"// fixture\n",
             "package.json": b'{"type":"module"}\n',
             "node_modules/effect/package.json": b'{"version":"fixture"}\n'}
    archive = base / (version + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = base / (version + ".json")
    manifest.write_text(json.dumps({"version": version, "sha256": checksum,
                                   "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}))
    manager = base / "systemctl.json"
    if not manager.exists():
        manager.write_text(json.dumps({"units": {name: {"enabled": False, "active": False}
                                               for name in ("chaldea-quota.service", "chaldea-waits.service")},
                                      "calls": []}))
    monkeypatch.setenv("PATH", str(ROOT / "tests/fake-bin") + ":" + os.environ["PATH"])
    monkeypatch.setenv("FAKE_SYSTEMCTL_STATE", str(manager))
    monkeypatch.setenv("FAKE_SYSTEMCTL_UNIT_HOME", str(home))
    return {"fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid()},
            "ansible_python_interpreter": sys.executable,
            "chaldea_node_version": "26.10.0", "chaldea_client_enabled": True,
            "chaldea_client_version": version, "chaldea_client_sha256": checksum,
            "chaldea_client_archive_source": str(archive), "chaldea_client_manifest_source": str(manifest),
            "chaldea_client_waits_socket": str(home / ".cache/chaldea-waits.sock"),
            "chaldea_client_waits_environment": "fixture-environment",
            "chaldea_client_codex_home": str(home / ".codex"),
            "mcp_registrations_claude": [str(ROOT / "tests/fake-claude"), str(home / "claude-mcp.json")]}


def run(base, variables, check=False):
    safe(base)
    play = base / "client.yml"
    play.write_text(yaml.safe_dump([{"name": "Client role in scratch", "hosts": "localhost",
                                    "connection": "local", "gather_facts": False,
                                    "vars": variables, "roles": ["chaldea_client"]}]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play),
                             *(["--check", "--diff"] if check else [])],
                            env=env, cwd=ROOT, capture_output=True, text=True)
    return result


def provision():
    home = Path.home()
    safe(home)
    config = home / ".config/chaldea"
    config.mkdir(parents=True)
    for name in ("t3-token", "waits-t3-token", "waits-answer-token"):
        token = config / name
        token.write_text("FIXTURE-SECRET-NEVER-PRINT")
        token.chmod(0o600)


def success(result):
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FIXTURE-SECRET-NEVER-PRINT" not in result.stdout + result.stderr


def test_directory_provisioning_repairs_private_quota_state():
    home = Path.home()
    safe(home)
    assert home == Path(os.environ["HOME"]).resolve()
    base = home / "directory-fixture"
    base.mkdir()
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    canonical = yaml.safe_load((ROOT / "roles/chaldea_client/tasks/main.yml").read_text())
    names = {"Create client directories without touching other config or state",
             "Create private client-owned directories"}
    tasks = [task for task in canonical if task.get("name") in names]
    assert len(tasks) == 2
    assert all(task["ansible.builtin.file"]["state"] == "directory" for task in tasks)
    state = home / ".local/state/chaldea"
    generic = {home / ".local/share/chaldea": 0o755,
               home / ".config/systemd/user": 0o775,
               home / ".local/bin": 0o751}
    for path, mode in {
        **generic, state: 0o755,
        home / ".local/share/chaldea/releases": 0o700,
        home / ".cache/chaldea-client": 0o700,
        home / ".config/chaldea": 0o700,
    }.items():
        assert path.resolve().is_relative_to(home)
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)
    observer = state / "quota-observer.json"
    observer.write_bytes(b"quota fixture\n" + b"x" * (45878 - 14))
    observer.chmod(0o600)
    os.utime(observer, ns=(1700000000000000000, 1700000000000000000))

    def snapshot():
        st = observer.lstat()
        assert observer.is_file() and not observer.is_symlink()
        return (observer.read_bytes(), st.st_mode, st.st_uid, st.st_gid,
                st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

    before = snapshot()
    state_before = state.stat()
    assert state_before.st_mode & 0o777 == 0o755
    assert state_before.st_uid == before[2] == os.getuid()
    play = base / "directories.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Canonical directory tasks in scratch", "hosts": "localhost",
        "connection": "local", "gather_facts": False,
        "vars": defaults | {"fleet_home": str(home),
                            "ansible_python_interpreter": sys.executable},
        "tasks": tasks,
    }]))
    for attempt in range(2):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", str(play)], cwd=ROOT,
            env=dict(os.environ, ANSIBLE_LOCAL_TEMP=str(base / "ansible-local"),
                     ANSIBLE_REMOTE_TEMP=str(base / "ansible-remote")),
            capture_output=True, text=True)
        print(result.stdout, result.stderr)
        success(result)
        assert ("changed=1" if attempt == 0 else "changed=0") in result.stdout
        st = state.stat()
        assert st.st_mode & 0o777 == 0o700
        assert (st.st_uid, st.st_gid, st.st_ino) == (
            state_before.st_uid, state_before.st_gid, state_before.st_ino)
        assert snapshot() == before
        for path, mode in generic.items():
            assert path.stat().st_mode & 0o777 == mode


def test_apply_migration_units_and_idempotence(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    variables |= {"chaldea_client_quota_enabled": True, "chaldea_client_waits_enabled": True}
    provision()
    home = Path.home()
    app = home / ".local/share/chaldea/app"
    (app / ".git").mkdir(parents=True)
    (app / "operator-note").write_text("preserve checkout")
    state = home / ".local/state/chaldea"
    state.mkdir(parents=True)
    (state / "waits.sqlite").write_bytes(b"database sentinel")
    (home / ".config/chaldea/other.json").write_text("preserve config")
    units = home / ".config/systemd/user"
    units.mkdir(parents=True)
    for name in ("quota", "waits"):
        (units / ("chaldea-" + name + ".service")).write_text("hand-made unit")
    result = run(tmp_path, variables)
    success(result)
    root = home / ".local/share/chaldea"
    assert (root / "current").resolve() == root / "releases/client-v9.0.0"
    assert not app.exists()
    assert (root / "app.pre-fleet/operator-note").read_text() == "preserve checkout"
    assert (state / "waits.sqlite").read_bytes() == b"database sentinel"
    assert (home / ".config/chaldea/other.json").read_text() == "preserve config"
    for name in ("quota", "waits"):
        unit = (units / ("chaldea-" + name + ".service")).read_text()
        assert "%h/.local/share/chaldea/current/bin/chaldea" in unit
        assert str(home) not in unit and "/home/igor" not in unit
        assert list(units.glob("chaldea-" + name + ".service.*~")), "keep replaced hand-made unit backup"
    quota = json.loads((home / ".config/chaldea/quota.json").read_text())
    assert quota["contexts"][0] == {"providers": ["codex"], "home": str(home),
                                   "codexHome": str(home / ".codex"),
                                   "command": str(home / ".local/share/mise/shims/codex"),
                                   "assertRuntimeHome": False}
    waits = json.loads((home / ".config/chaldea/waits.json").read_text())
    assert waits["environment"] == "fixture-environment"
    assert waits["tokenFile"] == str(home / ".config/chaldea/waits-t3-token")
    manager = json.loads((tmp_path / "systemctl.json").read_text())
    assert all(u["active"] and u["enabled"] for u in manager["units"].values())
    route = json.loads((home / ".config/chaldea/route.json").read_text())
    capacity = json.loads((home / ".config/chaldea/capacity.json").read_text())
    assert route["claudeUsage"] == {"enabled": False, "providerInstanceId": "claudeAgent"}
    assert route["paceMargin"] == capacity["paceMargin"] == 0.10
    assert route["minimumRemaining"] == capacity["minimumRemaining"] == 0.10
    assert route["quotaMaxAgeMs"] == capacity["maxAgeMs"] == 900000
    assert route["failureMargin"] == 0.10 and route["minimumTurns"] == 100
    assert route["analyticsMaxAgeMs"] == 259200000
    assert capacity["minimumResetLeadHours"] == 72
    assert capacity["providers"] == {}
    for name in ("route", "capacity"):
        assert (home / f".config/chaldea/{name}.json").stat().st_mode & 0o777 == 0o600
    for check in (False, True):
        repeated = run(tmp_path, variables, check=check)
        success(repeated)
        assert "changed=0" in repeated.stdout, repeated.stdout
    assert (home / ".local/bin/chaldea").is_file()
    assert "/current/bin/chaldea" in (home / ".local/bin/chaldea").read_text()


def test_route_target_overrides_render_once(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    variables["chaldea_client_route_targets"] = {
        "minimumTurns": 200, "failureMargin": 0.05,
        "pins": {"bulk-read": {"model": "gpt-6-luna"}},
        "bans": ["*sonnet*"], "probationShare": 0.2,
    }
    success(run(tmp_path, variables))

    def unique(items):
        result = {}
        for key, value in items:
            assert key not in result, f"duplicate route key: {key}"
            result[key] = value
        return result

    route = json.loads((Path.home() / ".config/chaldea/route.json").read_text(),
                       object_pairs_hook=unique)
    assert route["minimumTurns"] == 200
    assert route["failureMargin"] == 0.05
    assert route["pins"]["bulk-read"]["model"] == "gpt-6-luna"
    assert route["probationShare"] == 0.2
    assert route["paceMargin"] == 0.10


@pytest.mark.parametrize("failure", ["missing", "mode", "symlink", "owner"])
def test_secret_refusal_precedes_writes_and_unit_calls(tmp_path, monkeypatch, failure):
    variables = fixture(tmp_path, monkeypatch)
    variables |= {"chaldea_client_quota_enabled": True, "chaldea_client_waits_enabled": True}
    provision()
    token = Path.home() / ".config/chaldea/waits-answer-token"
    if failure == "missing":
        token.unlink()
    elif failure == "mode":
        token.chmod(0o644)
    elif failure == "symlink":
        token.unlink()
        token.symlink_to("waits-t3-token")
    else:
        variables["ansible_facts"]["user_uid"] = os.getuid() + 1
    result = run(tmp_path, variables)
    assert result.returncode != 0
    assert "Refusing to start" in result.stdout
    assert "FIXTURE-SECRET-NEVER-PRINT" not in result.stdout + result.stderr
    assert not (Path.home() / ".local/share/chaldea").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]


@pytest.mark.parametrize("linked_parent", [False, True])
def test_disabled_units_need_no_secrets_and_upgrade_retains_one_previous(tmp_path, monkeypatch, linked_parent):
    if linked_parent:
        safe(tmp_path)
        home = Path.home()
        (home / "share-data").mkdir()
        (home / ".local").mkdir()
        (home / ".local/share").symlink_to(home / "share-data", target_is_directory=True)
    for version in ("client-v9.0.0", "client-v9.0.1", "client-v9.0.2"):
        variables = fixture(tmp_path, monkeypatch, version)
        success(run(tmp_path, variables))
    root = Path.home() / ".local/share/chaldea"
    assert sorted(p.name for p in (root / "releases").iterdir()) == ["client-v9.0.1", "client-v9.0.2"]
    assert (root / "previous").resolve() == (root / "releases/client-v9.0.1").resolve()
    cache = Path.home() / ".cache/chaldea-client"
    assert sorted(p.name for p in cache.iterdir()) == [
        "client-v9.0.1.json", "client-v9.0.1.tar.gz", "client-v9.0.2.json", "client-v9.0.2.tar.gz"]
    assert not (Path.home() / ".config/chaldea/t3-token").exists()
    mcp = json.loads((Path.home() / ".config/chaldea/mcp.json").read_text())
    assert mcp["environment"] == "routing-only"
    assert mcp["socket"] == variables["chaldea_client_waits_socket"]
    assert not (Path.home() / ".config/chaldea/waits.json").exists()
    assert json.loads((Path.home() / ".config/chaldea/route.json").read_text())["claudeUsage"]["enabled"] is False
    manager = json.loads((tmp_path / "systemctl.json").read_text())
    assert all(not u["enabled"] and not u["active"] for u in manager["units"].values())


@pytest.mark.parametrize("failure", ["checksum", "manifest", "traversal", "symlink"])
def test_release_refusals_leave_current_and_legacy_untouched(tmp_path, monkeypatch, failure):
    variables = fixture(tmp_path, monkeypatch)
    app = Path.home() / ".local/share/chaldea/app"
    (app / ".git").mkdir(parents=True)
    if failure == "checksum":
        variables["chaldea_client_sha256"] = "0" * 64
    else:
        manifest_path = Path(variables["chaldea_client_manifest_source"])
        manifest = json.loads(manifest_path.read_text())
        if failure == "manifest":
            manifest["version"] = "client-v0.0.0"
        else:
            archive = Path(variables["chaldea_client_archive_source"])
            name = "../escape" if failure == "traversal" else "bin/chaldea"
            with tarfile.open(archive, "w:gz") as tar:
                for path in ("bin/chaldea", "src/cli.ts", "package.json", *([name] if name != "bin/chaldea" else [])):
                    entry = tarfile.TarInfo(path)
                    if path == name and failure == "symlink":
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = "/outside"
                        tar.addfile(entry)
                    else:
                        tar.addfile(entry, io.BytesIO())
            manifest["files"] = {p: hashlib.sha256(b"").hexdigest()
                                 for p in ("bin/chaldea", "src/cli.ts", "package.json", name)}
            manifest["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            variables["chaldea_client_sha256"] = manifest["sha256"]
        manifest_path.write_text(json.dumps(manifest))
    result = run(tmp_path, variables)
    assert result.returncode != 0
    assert not (app.parent / "current").exists()
    assert app.exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]


def test_interrupted_unit_reload_retries_before_retiring_checkout(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    variables |= {"chaldea_client_quota_enabled": True, "chaldea_client_waits_enabled": True}
    provision()
    home = Path.home()
    app = home / ".local/share/chaldea/app"
    (app / ".git").mkdir(parents=True)
    manager = tmp_path / "systemctl.json"
    state = json.loads(manager.read_text())
    for unit in state["units"].values():
        unit.update(active=True, enabled=True)  # Hand-made services are already running.
    manager.write_text(json.dumps(state))
    failure = home / "fail-once"
    failure.touch()
    monkeypatch.setenv("FAKE_SYSTEMCTL_FAIL_ONCE", str(failure))
    first = run(tmp_path, variables)
    assert first.returncode != 0
    assert app.exists()
    marker = home / ".cache/chaldea-client/restart-required"
    assert marker.exists()
    assert "/current/bin/chaldea" in (home / ".config/systemd/user/chaldea-waits.service").read_text()
    result = run(tmp_path, variables)
    success(result)
    assert not marker.exists()
    assert not app.exists()
    assert (app.parent / "app.pre-fleet/.git").exists()
    calls = json.loads((tmp_path / "systemctl.json").read_text())["calls"]
    assert sum(call[0] == "daemon-reload" for call in calls) >= 3
    assert ["restart", "chaldea-quota.service"] in calls
    assert ["restart", "chaldea-waits.service"] in calls
    for config in (home / ".codex/config.toml", home / "claude-mcp.json"):
        assert "/current/bin/chaldea" in config.read_text()
    repeated = run(tmp_path, variables)
    success(repeated)
    assert "changed=0" in repeated.stdout, repeated.stdout


def test_unexpected_current_refuses_before_replacing_units(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    home = Path.home()
    current = home / ".local/share/chaldea/current"
    current.mkdir(parents=True)
    units = home / ".config/systemd/user"
    units.mkdir(parents=True)
    old = units / "chaldea-quota.service"
    old.write_text("hand-made unit")
    result = run(tmp_path, variables)
    assert result.returncode != 0
    assert old.read_text() == "hand-made unit"
    assert not (home / ".cache/chaldea-client").exists()



def test_explicit_rollback_history_preserves_payloads_and_cache(tmp_path, monkeypatch):
    for version in ("client-v0.2.0", "client-v0.3.0"):
        variables = fixture(tmp_path, monkeypatch, version)
        result = run(tmp_path, variables)
        print(result.stdout, result.stderr)
        success(result)
    root = Path.home() / ".local/share/chaldea"
    cache = Path.home() / ".cache/chaldea-client"
    history = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())[
        "chaldea_client_retained_versions"]
    assert history == ["client-v0.2.0", "client-v0.3.0", "client-v0.4.0", "client-v0.4.2", "client-v0.4.7"]

    def snapshot():
        paths = []
        for version in ("client-v0.2.0", "client-v0.3.0"):
            release = root / "releases" / version
            paths.extend([release, *release.rglob("*"), cache / (version + ".json"),
                          cache / (version + ".tar.gz")])
        result = {}
        for path in paths:
            st = path.lstat()
            result[str(path)] = (path.read_bytes() if path.is_file() else None,
                                 st.st_mode, st.st_uid, st.st_gid, st.st_mtime_ns,
                                 st.st_ino, st.st_size)
        return result

    before = snapshot()
    # Managed but unlisted candidates must still be collected.
    stale = root / "releases/client-v0.1.0"
    stale.mkdir(mode=0o700)
    (stale / "sentinel").write_bytes(b"unlisted fixture")
    for suffix in (".json", ".tar.gz"):
        (cache / ("client-v0.1.0" + suffix)).write_bytes(b"unlisted fixture")
    # Nonmanaged names remain outside GC's existing path boundary.
    (cache / "operator-note").write_bytes(b"preserve unmanaged")
    variables = fixture(tmp_path, monkeypatch, "client-v0.4.7")
    variables["chaldea_client_retained_versions"] = history
    for attempt in range(2):
        result = run(tmp_path, variables)
        print(result.stdout, result.stderr)
        success(result)
        if attempt:
            assert "changed=0" in result.stdout, result.stdout
        assert snapshot() == before
        assert sorted(p.name for p in (root / "releases").iterdir()) == [
            "client-v0.2.0", "client-v0.3.0", "client-v0.4.7"]
        assert sorted(p.name for p in cache.iterdir()) == [
            "client-v0.2.0.json", "client-v0.2.0.tar.gz",
            "client-v0.3.0.json", "client-v0.3.0.tar.gz",
            "client-v0.4.7.json", "client-v0.4.7.tar.gz", "operator-note"]
        assert (root / "current").resolve() == root / "releases/client-v0.4.7"
        assert (root / "previous").resolve() == root / "releases/client-v0.3.0"


@pytest.mark.parametrize("retained", [
    "client-v0.2.0", {"client-v0.2.0": True}, None, 1,
    ["client-v0.2.0"] * 2,
    ["client-v0.1." + str(n) for n in range(6)],
    [1], ["../client-v0.2.0"], ["/client-v0.2.0"],
    ["client-v0.2.0/../escape"], ["client-v00.2.0"],
    ["client-v0.2.0\n"], ["client-v0.2.0-rc1"],
])
def test_invalid_rollback_history_refuses_before_writes(tmp_path, monkeypatch, retained):
    variables = fixture(tmp_path, monkeypatch)
    variables["chaldea_client_retained_versions"] = retained
    result = run(tmp_path, variables)
    print(result.stdout, result.stderr)
    assert result.returncode != 0
    assert "Validate client pins and host configuration before changing files" in result.stdout
    assert "Create client directories" not in result.stdout
    assert not (Path.home() / ".local").exists()
    assert not (Path.home() / ".config").exists()
    assert not (Path.home() / ".cache").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]


def test_fresh_check_does_not_write_or_call_user_manager(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    success(run(tmp_path, variables, check=True))
    assert not (Path.home() / ".local/share/chaldea").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]
