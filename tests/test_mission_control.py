"""Real Ansible composition in scratch. UIDs/digests below are fixtures, never pins."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest
import yaml

from client_artifact_fixture import stage

ROOT = Path(__file__).resolve().parents[1]


def safe(path):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    assert path.is_relative_to(Path(os.environ["TMPDIR"]))
    return path


def play(tmp_path, host, tasks=None, roles=None, values=None, check=False, inventory=None):
    safe(tmp_path)
    source = tmp_path / "play.yml"
    source.write_text(yaml.safe_dump([dict(name="Mission Control scratch fixture", hosts=host,
        connection="local", gather_facts=False, vars=values or {}, **({"tasks": tasks} if tasks is not None else {"roles": roles}))]))
    env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible-local"),
        ANSIBLE_REMOTE_TEMP=str(tmp_path / "ansible-remote"), ANSIBLE_LIBRARY=str(ROOT / "library"),
        ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    return subprocess.run(["ansible-playbook", "-i", inventory or host + ",", str(source),
        *(["--check", "--diff"] if check else [])], env=env, text=True, capture_output=True)


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_four_host_seven_default_outputs_and_helper_bytes(tmp_path):
    before = json.loads((ROOT / "tests/fixtures/mission-control-before.json").read_text())
    defaults = {}
    for role in ("chaldea_client", "chaldea_token_helper", "akasha_collector", "mission_control_runtime",
                 "mission_control_capture", "mission_control_reader"):
        defaults.update(yaml.safe_load((ROOT / "roles" / role / "defaults/main.yml").read_text()))
    defaults.update(yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text()))
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    for host, values in hosts.items():
        directory = tmp_path / host
        directory.mkdir()
        tasks = []
        for index, (path, text) in enumerate(before.items()):
            baseline = directory / f"before-{index}.j2"
            baseline.write_text(text)
            for label, src in (("before", str(baseline)), ("after", str(ROOT / path))):
                tasks.append(dict(name=f"Render {label} {index}", **{"ansible.builtin.template":
                    dict(src=src, dest=str(directory / f"{label}-{index}"), mode="0600")}))
        result = play(tmp_path, host, tasks=tasks, values=defaults | values | dict(
            fleet_home=str(Path.home()), ansible_facts=dict(user_dir=str(Path.home()), user_uid=0),
            akasha_collector_mission_control_snapshot_file="",  # Default-output baseline; activation is checked below.
            chaldea_host_artifact_root=str(tmp_path / "host")))
        ok(result)
        for index in range(7):
            assert (directory / f"before-{index}").read_bytes() == (directory / f"after-{index}").read_bytes()
        if snapshot := values.get("akasha_collector_mission_control_snapshot_file"):
            active = defaults | values | dict(fleet_home=str(Path.home()),
                chaldea_host_artifact_root=str(tmp_path / "host"))
            for filename, expected in (
                ("akasha-collector.j2", f'export AKASHA_MISSION_CONTROL_SNAPSHOT_FILE="{snapshot}"'),
                ("akasha-collector.service.j2", f'Environment="AKASHA_MISSION_CONTROL_SNAPSHOT_FILE={snapshot}"'),
            ):
                target = directory / filename
                result = play(tmp_path, host, tasks=[dict(name="Render actual collector input",
                    **{"ansible.builtin.template": dict(src=str(ROOT / "roles/akasha_collector/templates" / filename),
                        dest=str(target), mode="0600")})], values=active)
                ok(result)
                assert expected in target.read_text().splitlines()
        # New roles are actually inert through the Ansible executor.
        result = play(tmp_path, host, roles=["mission_control_runtime", "mission_control_capture", "mission_control_reader"],
                      values=dict(fleet_home=str(Path.home())))
        ok(result)
        assert "changed=0" in result.stdout
    assert len(hosts) == 4


def fixture_role(tmp_path, name):
    """Relocate file destinations only; account/systemd effects stay disposable."""
    safe(tmp_path)
    protected_opt = tmp_path / "protected-opt"
    protected_opt.mkdir(mode=0o755, exist_ok=True)
    role = tmp_path / "roles" / name
    shutil.copytree(ROOT / "roles" / name, role)
    replacements = {"/opt/chaldea-mission-control": str(tmp_path / "runtime"),
                    "/opt/chaldea/node/bin/node": str(tmp_path / "node/bin/node"),
                    "/home/igor": str(Path.home()),
                    "/etc/systemd/system": str(tmp_path / "units"),
                    "/etc/mission-control-reader": str(tmp_path / "reader-config"),
                    "/var/lib/mission-control-reader": str(tmp_path / "reader-state"),
                    "/var/cache/mission-control": str(tmp_path / "cache")}
    for file in role.rglob("*"):
        if not file.is_file():
            continue
        text = file.read_text()
        for old, new in replacements.items():
            text = text.replace(old, new)
        if name == "mission_control_runtime":
            text = text.replace("- /opt\n", "- " + str(protected_opt) + "\n")
            text = text.replace("item.stat.uid == 0", "item.stat.uid == " + str(os.getuid()))
        if name == "mission_control_capture":
            text = text.replace("default(-1) == 1000", "default(-1) == " + str(os.getuid()))
        file.write_text(text)
    node = tmp_path / "node/bin/node"
    node.parent.mkdir(parents=True, exist_ok=True)
    node.write_text("#!/bin/sh\\nexit 0\\n")
    node.chmod(0o755)
    tasks_file = role / "tasks/main.yml"
    tasks = yaml.safe_load(tasks_file.read_text())
    def relocate(rows):
        kept = []
        for row in rows:
            if any(key in row for key in ("ansible.builtin.user", "ansible.builtin.group")):
                continue
            if "block" in row:
                row["block"] = relocate(row["block"])
            if "ansible.builtin.systemd_service" in row:
                row = dict(name=row["name"], **{"ansible.builtin.fail": dict(msg="unit manager must not run in cold check")},
                           when=row.get("when"))
            for module in ("ansible.builtin.file", "ansible.builtin.template", "ansible.builtin.copy", "ansible.builtin.get_url"):
                if module in row:
                    for field in ("owner", "group"):
                        if field in row[module]:
                            row[module][field] = str(os.getuid() if field == "owner" else os.getgid())
            if "loop" in row and isinstance(row["loop"], list):
                for item in row["loop"]:
                    if isinstance(item, dict) and "owner" in item:
                        item["owner"] = str(os.getuid())
            kept.append(row)
        return kept
    tasks_file.write_text(yaml.safe_dump(relocate(tasks)))
    (tmp_path / "units").mkdir(exist_ok=True)
    return str(role)


def test_reader_exact_contract_real_writes_cold_check_and_second_real(tmp_path):
    role = fixture_role(tmp_path, "mission_control_reader")
    values = dict(mission_control_reader_enabled=True, mission_control_runtime_enabled=True,
        mission_control_reader_uid=23017,  # fixture only, production remains null
        mission_control_reader_allowed_source_ids=["agent-a--mission-control"],
        mission_control_runtime_node="/bin/true", mission_control_runtime_release_root=str(tmp_path / "runtime"),
        mission_control_runtime_version="client-v9.8.7", mission_control_reader_cache_file=str(tmp_path / "cache/latest.json"),
        mission_control_reader_grants=[dict(uid=23017, audience="akasha", action="read", source="mission-control-reader",
            host="omarchy-normandy", kind="agent_status", profile="mission-control-reader", project="chaldea")])
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=values, check=True))
    # Service-manager calls are excluded for the real filesystem fixture.
    path = Path(role) / "tasks/main.yml"
    rows = yaml.safe_load(path.read_text())
    rows[0]["block"] = [r for r in rows[0]["block"] if "ansible.builtin.fail" not in r]
    path.write_text(yaml.safe_dump(rows))
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=values))
    config = json.loads((tmp_path / "reader-config/reader.json").read_text())
    assert config == dict(url="https://akasha.ryzhkov.dev", tokenHelper="/usr/local/bin/chaldea-token-helper",
        source="mission-control-reader", host="omarchy-normandy", profile="mission-control-reader", project="chaldea",
        allowedSourceIds=["agent-a--mission-control"], cacheFile=str(tmp_path / "cache/latest.json"), refreshMs=5000)
    assert (tmp_path / "cache").stat().st_mode & 0o7777 == 0o2750
    assert (tmp_path / "reader-config/reader.json").stat().st_mode & 0o777 == 0o640
    assert (tmp_path / "reader-state").stat().st_mode & 0o777 == 0o700
    again = play(tmp_path, "omarchy-normandy", roles=[role], values=values)
    ok(again)
    assert "changed=0" in again.stdout
    for key, invalid in (("mission_control_reader_uid", None), ("mission_control_reader_uid", 1000),
                         ("mission_control_reader_allowed_source_ids", ["foreign"]), ("mission_control_reader_grants", [])):
        result = play(tmp_path, "omarchy-normandy", roles=[role], values=values | {key: invalid})
        assert result.returncode != 0
        assert "Require a selected dedicated UID" in result.stdout


def test_canonical_installer_side_by_side_and_real_role_idempotence(tmp_path):
    variables = stage(tmp_path / "artifact")
    role = fixture_role(tmp_path, "mission_control_runtime")
    for version, stamp in (("client-v0.0.1", 1), ("client-v0.0.2", 2)):
        old = tmp_path / "runtime/releases" / version
        old.mkdir(parents=True)
        (old / "sentinel").write_text(version)
        os.utime(old, (stamp, stamp))
    helper = tmp_path / "helper/client-v0.4.0"
    helper.mkdir(parents=True)
    (helper / "sentinel").write_bytes(b"old helper unchanged")
    values = dict(mission_control_runtime_enabled=True, mission_control_runtime_version=variables["chaldea_client_version"],
        mission_control_runtime_sha256=variables["chaldea_client_sha256"], mission_control_runtime_node=str(tmp_path / "node/bin/node"),
        mission_control_runtime_release_root=str(tmp_path / "runtime"),
        mission_control_runtime_archive_source=variables["chaldea_client_archive_source"],
        mission_control_runtime_manifest_source=variables["chaldea_client_manifest_source"])
    protected_opt = tmp_path / "protected-opt"
    protected_opt.chmod(0o777)
    try:
        refused = play(tmp_path, "fixture", roles=[role], values=values)
        assert refused.returncode != 0 and "Refuse writable or linked runtime ancestors" in refused.stdout
        assert not (tmp_path / "runtime/cache").exists()
        assert not (tmp_path / "runtime/releases/client-v9.8.7").exists()
    finally:
        protected_opt.chmod(0o755)
    ok(play(tmp_path, "fixture", roles=[role], values=values, check=True))
    ok(play(tmp_path, "fixture", roles=[role], values=values))
    again = play(tmp_path, "fixture", roles=[role], values=values)
    ok(again)
    assert "changed=0" in again.stdout
    assert (helper / "sentinel").read_bytes() == b"old helper unchanged"
    assert not (tmp_path / "runtime/releases/client-v0.0.1").exists()
    assert (tmp_path / "runtime/releases/client-v0.0.2/sentinel").exists()
    assert (tmp_path / "runtime/releases/client-v9.8.7/bin/chaldea").exists()
    drift = tmp_path / "runtime/releases/client-v9.8.7/src/cli.ts"
    drift.write_text("drift")
    refused = play(tmp_path, "fixture", roles=[role], values=values)
    assert refused.returncode != 0 and "immutable installed release differs" in refused.stdout


def test_capture_and_reader_units_offline_verification(tmp_path):
    from ansible.plugins.filter.core import FilterModule
    from jinja2 import Environment, StrictUndefined
    env = Environment(undefined=StrictUndefined)
    env.filters.update(FilterModule().filters())
    variables = dict(mission_control_runtime_node="/bin/true", mission_control_runtime_release_root="/fixture",
        mission_control_runtime_version="client-v9.8.7", mission_control_capture_home="/home/igor",
        mission_control_capture_snapshot_file="/home/igor/.local/state/chaldea/mission-control/latest.json")
    units = []
    for role, name in (("mission_control_capture", "mission-control-capture"), ("mission_control_reader", "mission-control-reader")):
        unit = tmp_path / (name + ".service")
        text = env.from_string((ROOT / "roles" / role / "templates" / (name + ".service.j2")).read_text()).render(variables)
        unit.write_text(text)
        units.append(str(unit))
        assert "NoNewPrivileges=" + ("yes" if "capture" in name else "no") in text
    runtime = tmp_path / "xdg"
    runtime.mkdir(mode=0o700)
    result = subprocess.run(["systemd-analyze", "--user", "verify", "--man=no", *units],
        env=dict(os.environ, XDG_RUNTIME_DIR=str(runtime)), text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
