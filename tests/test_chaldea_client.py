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
    return {"fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid()},
            "ansible_python_interpreter": sys.executable,
            "chaldea_node_version": "26.10.0", "chaldea_client_enabled": True,
            "chaldea_client_version": version, "chaldea_client_sha256": checksum,
            "chaldea_client_archive_source": str(archive), "chaldea_client_manifest_source": str(manifest),
            "chaldea_client_waits_socket": str(home / ".cache/chaldea-waits.sock"),
            "chaldea_client_waits_environment": "fixture-environment",
            "chaldea_client_codex_home": str(home / ".codex")}


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
                                   "command": str(home / ".local/share/mise/shims/codex")}
    waits = json.loads((home / ".config/chaldea/waits.json").read_text())
    assert waits["environment"] == "fixture-environment"
    assert waits["tokenFile"] == str(home / ".config/chaldea/waits-t3-token")
    manager = json.loads((tmp_path / "systemctl.json").read_text())
    assert all(u["active"] and u["enabled"] for u in manager["units"].values())
    for check in (False, True):
        repeated = run(tmp_path, variables, check=check)
        success(repeated)
        assert "changed=0" in repeated.stdout, repeated.stdout
    assert (home / ".local/bin/chaldea").is_file()
    assert "/current/bin/chaldea" in (home / ".local/bin/chaldea").read_text()


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


def test_disabled_units_need_no_secrets_and_upgrade_retains_one_previous(tmp_path, monkeypatch):
    for version in ("client-v9.0.0", "client-v9.0.1", "client-v9.0.2"):
        variables = fixture(tmp_path, monkeypatch, version)
        success(run(tmp_path, variables))
    root = Path.home() / ".local/share/chaldea"
    assert sorted(p.name for p in (root / "releases").iterdir()) == ["client-v9.0.1", "client-v9.0.2"]
    assert (root / "previous").resolve() == root / "releases/client-v9.0.1"
    assert not (Path.home() / ".config/chaldea/t3-token").exists()
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


def test_fresh_check_does_not_write_or_call_user_manager(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    success(run(tmp_path, variables, check=True))
    assert not (Path.home() / ".local/share/chaldea").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]
