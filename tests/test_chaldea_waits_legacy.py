"""Actual Ansible admission and rollback bytes in disposable scratch only."""
import hashlib
import os
from pathlib import Path

import pytest
import yaml

from test_chaldea_client import fixture, safe
from test_chaldea_waits_system import ROLE, TEMPLATES, context, owners, play

LEGACY = "26.10.0"
CURRENT = "26.12.0"
OVERRIDE = "chaldea_client_waits_legacy_user_node_version"


def task_sources():
    tasks = yaml.safe_load((ROLE / "tasks/waits-owner.yml").read_text())
    # Reuse the canonical stat/assert tasks; manager views use the existing
    # ownership fixture. No real system manager or system destination is used.
    validation = yaml.safe_load((ROLE / "tasks/waits-validate.yml").read_text())
    return validation + tasks[1:]


def legacy_fixture(tmp_path, case):
    safe(tmp_path)
    home = Path.home()
    unit = home / ".config/systemd/user/chaldea-waits.service"
    unit.parent.mkdir(parents=True)
    original = (TEMPLATES / "chaldea-waits.service.j2").read_bytes().replace(
        b"{{ chaldea_node_version }}", LEGACY.encode())
    assert len(original.splitlines()) == 29 and len(original) == 867
    assert hashlib.sha256(original).hexdigest() == "6f3ed0db9a9aa56cada7c723afdef1f5d4c3f46633f8c1fc5f7fd7ae401364c8"
    unit.write_bytes(original)
    unit.chmod(0o644)
    backup = unit.with_suffix(".service.pre-system")
    rows = owners()
    system = tmp_path / "system.service"
    rows[0]["item"]["item"]["path"] = str(unit)
    rows[1]["item"]["item"]["path"] = str(system)
    for row in rows:
        row["item"]["stdout_lines"][-1] = "FragmentPath=" + row["item"]["item"]["path"]
    variables = context() | {
        "fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid(), "user_gid": os.getgid()},
        "chaldea_node_version": CURRENT, "chaldea_client_waits_service_mode": "system",
        "chaldea_client_waits_enabled": True, "chaldea_client_waits_deadline": "",
        "chaldea_client_waits_status_read_restart": False, OVERRIDE: LEGACY,
        "chaldea_client_waits_owners": {"results": [r["item"] for r in rows]},
    }
    if case == "absent-override":
        variables.pop(OVERRIDE)
    elif case == "wrong-override":
        variables[OVERRIDE] = "26.11.0"
    elif case == "user-mode":
        variables["chaldea_client_waits_service_mode"] = "user"
    elif case == "waits-off":
        variables["chaldea_client_waits_enabled"] = False
    elif case == "drift":
        unit.write_bytes(original + b"# drift\n")
    elif case == "mode":
        unit.chmod(0o666)
    elif case == "owner":
        # The job maps only its own UID. Compare real stat with a foreign
        # expected fleet UID rather than trying to chown to an unmapped UID.
        variables["ansible_facts"]["user_uid"] = os.getuid() + 1
    elif case == "hardlink":
        os.link(unit, tmp_path / "hardlink")
    elif case == "symlink":
        other = tmp_path / "other.service"
        unit.rename(other)
        unit.symlink_to(other)
    elif case == "directory":
        unit.unlink()
        unit.mkdir()
    elif case == "missing":
        unit.unlink()
        rows[0]["item"]["stdout_lines"] = [
            "DropInPaths=", "ActiveState=inactive", "LoadState=not-found", "UnitFileState="]
    elif case in {"active", "enabled", "dropin", "alias", "unknown", "dual-active"}:
        lines = rows[0]["item"]["stdout_lines"]
        if case in {"active", "dual-active"}:
            lines[1] = "ActiveState=active"
            if case == "dual-active":
                rows[1]["item"]["stdout_lines"][1] = "ActiveState=active"
        elif case == "enabled":
            lines[2] = "UnitFileState=enabled"
        elif case == "dropin":
            lines[0] = "DropInPaths=/foreign.conf"
        elif case == "alias":
            lines[-1] = "FragmentPath=/foreign.service"
        else:
            lines[:] = ["LoadState=error"]
    elif case.startswith("backup-") or case.startswith("masked"):
        backup.write_bytes(original)
        backup.chmod(0o644)
        if case.endswith("foreign"):
            backup.write_bytes(b"foreign\n")
        elif case.endswith("mode"):
            backup.chmod(0o666)
        elif case.endswith("owner"):
            variables["ansible_facts"]["user_uid"] = os.getuid() + 1
        elif case.endswith("hardlink"):
            os.link(backup, tmp_path / "backup-link")
        elif case.endswith("symlink"):
            other = tmp_path / "backup.service"
            backup.rename(other)
            backup.symlink_to(other)
        if case.startswith("masked"):
            unit.unlink()
            unit.symlink_to("/dev/null")
            rows[0]["item"]["stdout_lines"] = [
                "DropInPaths=", "ActiveState=inactive", "LoadState=masked", "UnitFileState=masked"]
            if case == "masked-no-backup":
                backup.unlink()
            elif case == "masked-enabled":
                rows[0]["item"]["stdout_lines"][-1] = "UnitFileState=enabled"
    return variables, unit, backup, system, original


def admission(tmp_path, variables, system, tasks=None, after=()):
    # Render both current system module and lookup bytes independently of the
    # legacy lookup's template_vars. Real stat supplies the checksums/metadata.
    safe(tmp_path)
    role = tmp_path / "legacy-role"
    (role / "tasks").mkdir(parents=True, exist_ok=True)
    if not (role / "templates").exists():
        (role / "templates").symlink_to(TEMPLATES, target_is_directory=True)
    (role / "tasks/main.yml").write_text(yaml.safe_dump(
        (task_sources() if tasks is None else tasks) + list(after)))
    return play(tmp_path, variables, [
        {"name": "Render current system bytes", "ansible.builtin.template": {
            "src": str(TEMPLATES / "chaldea-waits-system.service.j2"),
            "dest": str(system), "mode": "0644"}},
        {"name": "Require current Node remains in system bytes", "ansible.builtin.assert": {
            "that": ["'/node/26.12.0/bin/node' in lookup('ansible.builtin.file', '" + str(system) + "')",
                     "'/node/26.10.0/bin/node' not in lookup('ansible.builtin.file', '" + str(system) + "')"]}},
        {"name": "Run canonical guards in role template context",
         "ansible.builtin.include_role": {"name": str(role)}},
    ])


@pytest.mark.parametrize("case", [
    "owned", "absent-override", "wrong-override", "user-mode", "waits-off",
    "drift", "mode", "owner", "hardlink", "symlink", "directory", "missing",
    "active", "enabled", "dropin", "alias", "unknown", "dual-active",
    "backup-exact", "backup-foreign", "backup-mode", "backup-owner",
    "backup-hardlink", "backup-symlink",
    "masked", "masked-no-backup", "masked-foreign", "masked-mode",
    "masked-owner", "masked-hardlink", "masked-symlink", "masked-enabled",
])
def test_legacy_admission(tmp_path, case):
    variables, unit, backup, system, original = legacy_fixture(tmp_path, case)
    before = {path: path.lstat() if path.exists() or path.is_symlink() else None
              for path in (unit, backup)}
    result = admission(tmp_path, variables, system)
    for path, stat in before.items():
        after = path.lstat() if path.exists() or path.is_symlink() else None
        if stat is None:
            assert after is None
        else:
            assert after is not None
            assert (after.st_ino, after.st_mode, after.st_uid, after.st_nlink, after.st_mtime_ns) == (
                stat.st_ino, stat.st_mode, stat.st_uid, stat.st_nlink, stat.st_mtime_ns)
    accepted = case in {"owned", "backup-exact", "masked"}
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if not accepted:
        assert '"evaluated_to": false' in result.stdout, result.stdout + result.stderr
    if case == "owned":
        assert not backup.exists()


@pytest.mark.parametrize("value", ["26.10", "v26.10.0", "26.10.0-rc1", "../26.10.0",
                                   "26.10.0\n", "26.10.0 ", 26, None, True])
def test_override_requires_exact_version(tmp_path, value):
    variables, _, _, system, _ = legacy_fixture(tmp_path, "owned")
    variables[OVERRIDE] = value
    result = admission(tmp_path, variables, system)
    assert result.returncode != 0, result.stdout + result.stderr


def test_default_override_is_empty():
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert defaults[OVERRIDE] == ""


def test_unavailable_manager_refuses_before_writes(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    variables |= {OVERRIDE: LEGACY, "chaldea_client_waits_service_mode": "system"}
    # Existing fake-manager mechanism fails its read when the state is missing.
    # This exercises the canonical command/failed_when, without host managers.
    (tmp_path / "systemctl.json").unlink()
    probe = yaml.safe_load((ROLE / "tasks/waits-owner.yml").read_text())[0]
    sentinel = tmp_path / "unexpected-write"
    result = play(tmp_path, variables, [
        probe,
        {"name": "Never reach mutation", "ansible.builtin.copy": {
            "content": "must not write", "dest": str(sentinel), "mode": "0600"}},
    ])
    assert result.returncode != 0 and "Never reach mutation" not in result.stdout
    assert not sentinel.exists() and not (Path.home() / ".config").exists()


def test_original_source_rejects_known_legacy_bytes(tmp_path):
    variables, _, backup, system, _ = legacy_fixture(tmp_path, "owned")
    # The job stages this exact file from the pinned Git base, with no source
    # substitution. Keep the regression proof available to independent review.
    baseline = os.environ.get("CHALDEA_LEGACY_OWNER_BASELINE")
    if not baseline:
        pytest.skip("set CHALDEA_LEGACY_OWNER_BASELINE to exact pinned base waits-owner.yml")
    assert baseline
    baseline_tasks = yaml.safe_load(Path(baseline).read_text())[1:]
    result = admission(tmp_path, variables, system, tasks=baseline_tasks)
    assert result.returncode != 0 and "Refuse foreign definitions" in result.stdout
    assert not backup.exists()


def test_backup_mask_resume_and_explicit_restoration(tmp_path):
    variables, unit, backup, system, original = legacy_fixture(tmp_path, "owned")
    canonical = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
    selected = [task for task in canonical if task["name"] in {
        "Preserve the old role-owned user unit for explicit rollback",
        "Mask the user unit so there can be only one waits database owner",
    }]
    assert len(selected) == 2 and selected[0]["ansible.builtin.copy"]["force"] is False
    result = admission(tmp_path, variables, system, after=selected)
    assert result.returncode == 0, result.stdout + result.stderr
    assert unit.is_symlink() and os.readlink(unit) == "/dev/null"
    assert backup.read_bytes() == original
    views = variables["chaldea_client_waits_owners"]["results"]
    views[0]["stdout_lines"] = [
        "DropInPaths=", "ActiveState=inactive", "LoadState=masked", "UnitFileState=masked"]
    result = admission(tmp_path, variables, system)
    assert result.returncode == 0, result.stdout + result.stderr
    assert backup.read_bytes() == original
    # Explicit rollback packet's filesystem steps, with no real service start.
    result = play(tmp_path, variables, [
        {"name": "Remove fixture mask", "ansible.builtin.file": {"path": str(unit), "state": "absent"}},
        {"name": "Restore exact original", "ansible.builtin.copy": {
            "src": str(backup), "dest": str(unit), "remote_src": True, "mode": "0644"}},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert unit.read_bytes() == backup.read_bytes() == original
    assert unit.stat().st_mode & 0o777 == 0o644
