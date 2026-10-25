"""Explicit waits runtime migration of the persistent system unit, in scratch only.

The installed system unit names the runtime it was rendered for, so exact
ownership admission refuses a new runtime selection before any write.
chaldea_client_waits_legacy_system_runtime admits only the role's exact rendering
with one named older runtime, with the usual custody and manager checks. These
tests use the canonical role tasks; no real system manager or system path is used.
"""
import hashlib
import os
from pathlib import Path

import pytest
import yaml

from test_chaldea_client import safe
from test_chaldea_session_profiles import ok, run
from test_chaldea_session_profiles_claude import CLAUDE, claude_layout
from test_chaldea_session_profiles import PROFILE
from test_chaldea_waits_legacy import system_owner_metadata, task_sources
from test_chaldea_waits_system import ROLE, TEMPLATES, context, owners, play

OVERRIDE = "chaldea_client_waits_legacy_system_runtime"
OLD = "client-v0.4.18"
NEW = "client-v0.4.20"
SYSTEM_TEMPLATE = str(TEMPLATES / "chaldea-waits-system.service.j2")
# Read-only operator evidence: the laptop's installed root-owned 0644 unit.
LAPTOP_UNIT_SHA256 = "9ef58ab4148b275744124cd66e3e0b9e1f38ce6f0cd725d559bcdc14f4b1387a"


def releases():
    return Path.home() / ".local/share/chaldea/releases"


def variables(tmp_path, system, case="legacy"):
    safe(tmp_path)
    home = Path.home()
    rows = owners()
    user = home / ".config/systemd/user/chaldea-waits.service"
    rows[0]["item"]["item"]["path"] = str(user)
    rows[0]["item"]["stdout_lines"] = [
        "DropInPaths=", "ActiveState=inactive", "LoadState=not-found", "UnitFileState="]
    rows[1]["item"]["item"]["path"] = str(system)
    rows[1]["item"]["stdout_lines"] = [
        "DropInPaths=", "ActiveState=active", "UnitFileState=enabled", "LoadState=loaded",
        "FragmentPath=" + str(system)]
    return context() | {
        "fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid(), "user_gid": os.getgid()},
        "chaldea_client_root": str(home / ".local/share/chaldea"),
        "chaldea_client_waits_resolved_runtime": str(releases() / NEW),
        "chaldea_client_waits_service_mode": "system", "chaldea_client_waits_enabled": True,
        "chaldea_client_waits_deadline": "", "chaldea_client_waits_status_read_restart": False,
        "chaldea_client_waits_legacy_user_node_version": "", OVERRIDE: str(releases() / OLD),
        "chaldea_client_waits_owners": {"results": [r["item"] for r in rows]},
    }


def render(tmp_path, values, runtime, dest):
    """Write the real Ansible template module bytes for one runtime."""
    result = play(tmp_path, values, [{
        "name": "Render the system unit for one runtime",
        "ansible.builtin.template": {"src": SYSTEM_TEMPLATE, "dest": str(dest), "mode": "0644"},
        "vars": {"chaldea_client_waits_resolved_runtime": runtime}}])
    assert result.returncode == 0, result.stdout + result.stderr
    return Path(dest).read_bytes()


def install_task(system):
    """The canonical install task with only its root owner and become removed."""
    tasks = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
    task = next(t for t in tasks if t["name"] == "Install the system waits definition")
    task.pop("become")
    module = task["ansible.builtin.template"]
    assert (module.pop("owner"), module.pop("group")) == ("root", "root")
    module.update(src=SYSTEM_TEMPLATE, dest=str(system))
    return task


def guards(tmp_path, values, after=(), system_uid=0):
    """Canonical validation, stat and ownership asserts in role template context.

    The resolved runtime is a fact, as waits-system-validate sets it, so the
    legacy lookup's template_vars must override fact precedence.
    """
    role = tmp_path / "migration-role"
    (role / "tasks").mkdir(parents=True, exist_ok=True)
    if not (role / "templates").exists():
        (role / "templates").symlink_to(TEMPLATES, target_is_directory=True)
    tasks = task_sources()
    index = next(i for i, task in enumerate(tasks) if task["name"] == "Model system owner metadata")
    tasks[index] = system_owner_metadata(system_uid)
    resolved = {"name": "Name the resolved runtime as a fact", "ansible.builtin.set_fact": {
        "chaldea_client_waits_resolved_runtime": values["chaldea_client_waits_resolved_runtime"]}}
    (role / "tasks/main.yml").write_text(yaml.safe_dump([resolved] + tasks + list(after)))
    return play(tmp_path, values, [{"name": "Run canonical guards", "ansible.builtin.include_role": {"name": str(role)}}])


def refused(result, message=None):
    assert result.returncode != 0, result.stdout + result.stderr
    assert '"evaluated_to": false' in result.stdout, result.stdout + result.stderr
    if message:
        assert message in result.stdout, result.stdout


UNIT = "Legacy runtime admission requires an existing regular system unit"
VALUE = "A legacy system runtime admission requires persistent system waits"


@pytest.mark.parametrize("case, message", [
    ("legacy", None), ("current", None), ("current-only", None),
    ("absent-override", "Refusing unknown waits ownership"),
    ("wrong-override", "Refusing unknown waits ownership"),
    ("drift", "Refusing unknown waits ownership"), ("mode", "Refusing unknown waits ownership"),
    ("owner", "Refusing unknown waits ownership"), ("hardlink", "Refusing unknown waits ownership"),
    ("symlink", UNIT), ("missing", UNIT),
    ("dropin", "Refusing unknown waits ownership"), ("alias", "Refusing unknown waits ownership"),
    ("dual-active", "Refusing unknown waits ownership"),
    ("outside-root", UNIT), ("equals-selected", UNIT),
    ("relative", VALUE), ("dotdot", VALUE), ("trailing-slash", VALUE), ("not-string", VALUE),
    ("user-mode", VALUE), ("deadline", VALUE),
])
def test_legacy_runtime_admission(tmp_path, case, message):
    system = tmp_path / "system.service"
    values = variables(tmp_path, system)
    old_bytes = render(tmp_path, values, str(releases() / OLD), system)
    if case in {"current", "current-only"}:
        render(tmp_path, values, str(releases() / NEW), system)
    if case in {"current-only", "absent-override"}:
        values.pop(OVERRIDE)
    elif case == "wrong-override":
        values[OVERRIDE] = str(releases() / "client-v0.4.19")
    elif case == "drift":
        system.write_bytes(old_bytes + b"# drift\n")
    elif case == "mode":
        system.chmod(0o666)
    elif case == "hardlink":
        os.link(system, tmp_path / "hardlink")
    elif case == "symlink":
        other = tmp_path / "other.service"
        system.rename(other)
        system.symlink_to(other)
    elif case == "missing":
        system.unlink()
        values["chaldea_client_waits_owners"]["results"][1]["stdout_lines"] = [
            "DropInPaths=", "ActiveState=inactive", "LoadState=not-found", "UnitFileState="]
    elif case == "dropin":
        values["chaldea_client_waits_owners"]["results"][1]["stdout_lines"][0] = "DropInPaths=/foreign.conf"
    elif case == "alias":
        values["chaldea_client_waits_owners"]["results"][1]["stdout_lines"][-1] = "FragmentPath=/foreign.service"
    elif case == "dual-active":
        values["chaldea_client_waits_owners"]["results"][0]["stdout_lines"][1] = "ActiveState=active"
    elif case == "outside-root":
        values[OVERRIDE] = "/home/other/.local/share/chaldea/releases/" + OLD
    elif case == "equals-selected":
        values[OVERRIDE] = values["chaldea_client_waits_resolved_runtime"]
    elif case == "relative":
        values[OVERRIDE] = "releases/" + OLD
    elif case == "dotdot":
        values[OVERRIDE] = str(releases() / NEW / ".." / OLD)
    elif case == "trailing-slash":
        values[OVERRIDE] = str(releases() / OLD) + "/"
    elif case == "not-string":
        values[OVERRIDE] = 18
    elif case == "user-mode":
        values |= {"chaldea_client_waits_service_mode": "user", "chaldea_client_session_policy_enabled": False}
    elif case == "deadline":
        values["chaldea_client_waits_deadline"] = "2026-10-25T12:00:00Z"
    before = system.lstat() if system.exists() or system.is_symlink() else None
    result = guards(tmp_path, values, system_uid=1001 if case == "owner" else 0)
    after = system.lstat() if system.exists() or system.is_symlink() else None
    # Admission never writes the unit, accepted or refused.
    assert (before and (before.st_ino, before.st_mtime_ns)) == (after and (after.st_ino, after.st_mtime_ns))
    if message is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        refused(result, message)


def test_migration_installs_the_current_unit_then_repeats_without_change(tmp_path):
    system = tmp_path / "system.service"
    values = variables(tmp_path, system)
    old_bytes = render(tmp_path, values, str(releases() / OLD), system)
    new_bytes = render(tmp_path, values, str(releases() / NEW), tmp_path / "expected.service")
    # The runtime path is the only difference between the two renderings.
    assert old_bytes != new_bytes
    assert old_bytes.replace(OLD.encode(), NEW.encode()) == new_bytes
    assert old_bytes.count(OLD.encode()) == 1
    # Without the admission, today's source refuses the known old unit.
    current_only = {k: v for k, v in values.items() if k != OVERRIDE}
    refused(guards(tmp_path, current_only, after=[install_task(system)]), "Refusing unknown waits ownership")
    assert system.read_bytes() == old_bytes
    # With it, the guards pass and the canonical task installs the current unit,
    # keeping the exact old bytes as its backup.
    first = guards(tmp_path, values, after=[install_task(system)])
    assert first.returncode == 0, first.stdout + first.stderr
    assert "changed=1" in first.stdout, first.stdout
    assert system.read_bytes() == new_bytes
    assert system.stat().st_mode & 0o777 == 0o644
    backups = [p for p in tmp_path.iterdir() if p.name.startswith("system.service.") and p.name.endswith("~")]
    assert [p.read_bytes() for p in backups] == [old_bytes]
    # Repeat with the admission still declared, then current-only: no change.
    for repeat in (values, current_only):
        again = guards(tmp_path, repeat, after=[install_task(system)])
        assert again.returncode == 0, again.stdout + again.stderr
        assert "changed=0" in again.stdout, again.stdout
        assert system.read_bytes() == new_bytes
    # Current-only source refuses the old unit again; nothing is written.
    system.write_bytes(old_bytes)
    refused(guards(tmp_path, current_only, after=[install_task(system)]), "Refusing unknown waits ownership")
    assert system.read_bytes() == old_bytes


def test_laptop_override_names_the_installed_unit_rendering(tmp_path):
    """The laptop's public values reproduce the observed installed unit digest."""
    safe(tmp_path)
    inventory = yaml.safe_load((Path(__file__).resolve().parents[1]
                                / "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml").read_text())
    home = "/home/igor"
    laptop = {"ansible_facts": {"user_uid": 1001, "user_gid": 1001}, "fleet_home": home,
              "chaldea_node_version": inventory["chaldea_node_version"],
              "chaldea_client_session_policy_enabled": inventory["chaldea_client_session_policy_enabled"],
              "chaldea_client_waits_deadline": inventory["chaldea_client_waits_deadline"]}
    old = render(tmp_path, laptop, inventory[OVERRIDE], tmp_path / "old.service")
    new = render(tmp_path, laptop, inventory["chaldea_client_waits_runtime_root"], tmp_path / "new.service")
    assert hashlib.sha256(old).hexdigest() == LAPTOP_UNIT_SHA256
    assert hashlib.sha256(new).hexdigest() != LAPTOP_UNIT_SHA256
    assert old.replace(OLD.encode(), NEW.encode()) == new


def test_codex_and_claude_profiles_change_only_their_helper_runtime(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch, keep_codex=True)
    old, new = str(releases() / OLD), str(releases() / NEW)

    def snapshot():
        files = {path: path.read_bytes() for directory in (case.directory, case.claude_dir)
                 for path in sorted(directory.iterdir())}
        files[case.config] = case.config.read_bytes()
        return files

    case.extra["chaldea_client_waits_resolved_runtime"] = old
    ok(run(case))
    before = snapshot()
    case.extra["chaldea_client_waits_resolved_runtime"] = new
    migrated = run(case)
    ok(migrated)
    assert "changed=0" not in migrated.stdout
    after = snapshot()
    assert list(after) == list(before)
    # Public files change only by the helper's runtime path; launchers also
    # repin the resulting digests. Natives, catalog and settings are untouched.
    digests = {}
    for path, raw in before.items():
        if path.name in {"mcp.json", "config.toml"}:
            assert old.encode() in raw, path
            assert raw.replace(old.encode(), new.encode()) == after[path], path
            digests[hashlib.sha256(raw).hexdigest()] = hashlib.sha256(after[path]).hexdigest()
    # Codex and Claude mcp.json are identical here, so three files give two digests.
    assert sum(path.name in {"mcp.json", "config.toml"} for path in before) == 3 and len(digests) == 2
    for path, raw in before.items():
        expected = raw.replace(old.encode(), new.encode())
        if path.name == "exec":
            for was, now in digests.items():
                expected = expected.replace(was.encode(), now.encode())
        elif path.name not in {"mcp.json", "config.toml"}:
            assert expected == raw, path
        assert expected == after[path], path
        assert old.encode() not in after[path], path
    assert after[case.directory / "exec"] != before[case.directory / "exec"]
    names = sorted(p.name for p in case.claude_dir.iterdir()), sorted(p.name for p in case.directory.iterdir())
    assert names[0] == ["claude", "claude-settings.json", "exec", "mcp.json"] and CLAUDE != PROFILE
    repeat = run(case)
    ok(repeat)
    assert "changed=0" in repeat.stdout, repeat.stdout
    assert snapshot() == after
