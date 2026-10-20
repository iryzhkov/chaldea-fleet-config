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
            packet = yaml.safe_load((ROOT / "playbooks/vars/mission-control-deployment.yml").read_text())
            active = defaults | values | packet | dict(fleet_home=str(Path.home()),
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
            text = text.replace("1001 if inventory_hostname == 'laptop' else 1000", str(os.getuid()))
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
            if row.get("name", "").endswith("identities for a materializable CHECK"):
                row["loop"] = [["passwd", str(os.getuid())], ["group", str(os.getgid())]]
            if "ansible.builtin.service_facts" in row:
                row.pop("ansible.builtin.service_facts")
                row["ansible.builtin.set_fact"] = dict(ansible_facts=dict(
                    services="{{ fixture_services | default({}) }}"))
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
    cold = play(tmp_path, "omarchy-normandy", roles=[role], values=values, check=True)
    ok(cold)
    assert "Cold CHECK defers staging" in cold.stdout
    assert not (tmp_path / "reader-config").exists() and not (tmp_path / "cache").exists()
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
        checked = play(tmp_path, "omarchy-normandy", roles=[role], values=values | {key: invalid}, check=True)
        assert checked.returncode != 0 and "Require a selected dedicated UID" in checked.stdout

    prospective: dict = values | dict(mission_control_pc_permission=True,
        mission_control_reader_allowed_source_ids=["agent-a--mission-control", "omarchy-pc--mission-control"])
    before = (tmp_path / "reader-config/reader.json").read_bytes()
    denied = play(tmp_path, "omarchy-normandy", roles=[role],
        values=prospective | dict(mission_control_pc_permission=False))
    assert denied.returncode != 0
    assert (tmp_path / "reader-config/reader.json").read_bytes() == before
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=prospective))
    assert json.loads((tmp_path / "reader-config/reader.json").read_text())["allowedSourceIds"] == prospective["mission_control_reader_allowed_source_ids"]
    for b, laptop in [(True, False), (False, True), (True, True)]:
        remaining = prospective | dict(mission_control_agent_b_permission=b,
            mission_control_laptop_permission=laptop, mission_control_laptop_qualified=True,
            mission_control_reader_allowed_source_ids=prospective["mission_control_reader_allowed_source_ids"] +
                (["agent-b--mission-control"] if b else []) +
                (["omarchy-macbook-air-igor--mission-control"] if laptop else []))
        if laptop:
            denied = play(tmp_path, "omarchy-normandy", roles=[role],
                values=remaining | dict(mission_control_laptop_qualified=False))
            assert denied.returncode != 0
        ok(play(tmp_path, "omarchy-normandy", roles=[role], values=remaining))
        assert json.loads((tmp_path / "reader-config/reader.json").read_text())["allowedSourceIds"] == remaining["mission_control_reader_allowed_source_ids"]

    # Optional Events/Ops reads: explicit opt-in only, never emitted when off.
    config = tmp_path / "reader-config/reader.json"
    legacy = config.read_bytes()
    assert "operationsEnabled" not in json.loads(legacy)
    row: dict = copy.deepcopy(values["mission_control_reader_grants"][0])  # type: ignore[index]
    operations: dict = remaining | dict(mission_control_reader_operations_enabled=True,
        mission_control_reader_grants=[row, row | dict(kind="job_finished"), row | dict(kind="report")])
    assert len(operations["mission_control_reader_allowed_source_ids"]) == 4
    for invalid in (dict(mission_control_reader_operations_enabled="true"),
                    dict(mission_control_reader_grants=[row]),
                    dict(mission_control_reader_grants=[row, row | dict(kind="job_finished")]),
                    dict(mission_control_reader_grants=[row, row | dict(kind="report"), row | dict(kind="job_finished")]),
                    dict(mission_control_reader_grants=operations["mission_control_reader_grants"] + [row | dict(kind="tool_call")]),
                    dict(mission_control_reader_grants=[row, row | dict(kind="job_finished", project="homelab"), row | dict(kind="report")]),
                    dict(mission_control_runtime_version="client-v0.4.8"),
                    dict(mission_control_agent_b_permission=False, mission_control_reader_allowed_source_ids=
                         ["agent-a--mission-control", "omarchy-pc--mission-control", "omarchy-macbook-air-igor--mission-control"])):
        denied = play(tmp_path, "omarchy-normandy", roles=[role], values=operations | invalid)
        assert denied.returncode != 0 and "Require a selected dedicated UID" in denied.stdout, invalid
        assert config.read_bytes() == legacy
    # Legacy grants with operations explicitly off keep exactly the old file bytes.
    unchanged = play(tmp_path, "omarchy-normandy", roles=[role], values=remaining | dict(
        mission_control_reader_operations_enabled=False))
    ok(unchanged)
    assert "changed=0" in unchanged.stdout and config.read_bytes() == legacy
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=operations))
    assert json.loads(config.read_text()) == json.loads(legacy) | dict(operationsEnabled=True)
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=remaining))
    assert config.read_bytes() == legacy


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
    variables = dict(inventory_hostname="agent-a", mission_control_runtime_node="/bin/true", mission_control_runtime_release_root="/fixture",
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


def instrument_activation(role, tmp_path):
    """Replace only OS accounts/manager boundaries; execute real Ansible task flow."""
    helper = tmp_path / "manager.py"
    helper.write_text("""import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
state = json.loads(p.read_text()) if p.exists() else {}
args = json.loads(sys.argv[2])
with p.with_suffix('.events').open('a') as out:
    out.write(json.dumps(args) + '\\n')
name = args.get('name', '')
changed = bool(args.get('daemon_reload', False))
if name:
    prior = state.get(name, {})
    desired = dict(enabled=args.get('enabled', prior.get('enabled', False)),
                   state='stopped' if args.get('state') == 'stopped' else 'started')
    changed |= prior != desired or args.get('state') == 'restarted'
    state[name] = desired
p.write_text(json.dumps(state))
print('CHANGED' if changed else 'UNCHANGED')
""")
    # Keep the manager's loaded command separate from the running process.
    original = helper.read_text()
    original = original.replace("args = json.loads(sys.argv[2])", """if sys.argv[2] == '--show':
    print('MainPID=' + ('42' if state.get('_running') else '0'))
    unit = p.parent / 'units/mission-control-capture.service'
    disk = next((x.removeprefix('ExecStart=') for x in unit.read_text().splitlines() if x.startswith('ExecStart=')), '')
    print('NeedDaemonReload=' + ('yes' if state.get('_loaded') != disk else 'no'))
    sys.exit(0)
args = json.loads(sys.argv[2])""")
    original = original.replace("p.write_text(json.dumps(state))", """if name == 'mission-control-capture.service':
    unit = p.parent / 'units/mission-control-capture.service'
    disk = next(x.removeprefix('ExecStart=') for x in unit.read_text().splitlines() if x.startswith('ExecStart='))
    if args.get('daemon_reload') or '_loaded' not in state:
        state['_loaded'] = disk
    if args.get('state') == 'restarted' or not state.get('_running'):
        state['_running'] = state['_loaded']
    proc = p.parent / 'proc/42/cmdline'
    proc.parent.mkdir(parents=True, exist_ok=True)
    proc.write_bytes(('\\0'.join(state['_running'].split()) + '\\0').encode())
p.write_text(json.dumps(state))""")
    helper.write_text(original)
    for source in Path(role).joinpath("tasks").glob("*.yml"):
        def rewrite(rows):
            result = []
            for row in rows:
                if "block" in row:
                    row["block"] = rewrite(row["block"])
                if "ansible.builtin.service_facts" in row:
                    row.pop("ansible.builtin.service_facts")
                    row["ansible.builtin.set_fact"] = dict(ansible_facts=dict(
                        services="{{ fixture_services | default({}) }}"))
                if row.get("ansible.builtin.command", {}).get("argv", [None])[0] == "systemctl":
                    assert row["ansible.builtin.command"]["argv"] == [
                        "systemctl", "show", "mission-control-capture.service", "--property=MainPID,NeedDaemonReload"]
                    row["ansible.builtin.command"]["argv"] = [
                        sys.executable, str(helper), str(tmp_path / "manager.json"), "--show"]
                if "ansible.builtin.slurp" in row:
                    row["ansible.builtin.slurp"]["src"] = row["ansible.builtin.slurp"]["src"].replace(
                        "/proc/", str(tmp_path / "proc") + "/")
                if "ansible.builtin.systemd_service" in row:
                    args = row.pop("ansible.builtin.systemd_service")
                    row["ansible.builtin.command"] = dict(argv=[
                        sys.executable, str(helper), str(tmp_path / "manager.json"),
                        "{{ fixture_manager_args | to_json }}"])
                    row["vars"] = dict(fixture_manager_args=args)
                    row["register"] = "fixture_manager"
                    row["changed_when"] = "fixture_manager.stdout == 'CHANGED'"
                result.append(row)
            return result
        source.write_text(yaml.safe_dump(rewrite(yaml.safe_load(source.read_text()))))


def test_reader_stage_refusal_and_in_memory_activation(tmp_path):
    role = fixture_role(tmp_path, "mission_control_reader")
    instrument_activation(role, tmp_path)
    values = dict(mission_control_reader_enabled=True, mission_control_runtime_enabled=True,
        mission_control_reader_uid=23017,
        mission_control_reader_allowed_source_ids=["agent-a--mission-control"],
        mission_control_runtime_node="/bin/true", mission_control_runtime_release_root="/fixture",
        mission_control_runtime_version="client-v9.8.7", mission_control_reader_cache_file=str(tmp_path / "cache/latest.json"),
        mission_control_reader_grants=[dict(uid=23017, audience="akasha", action="read",
            source="mission-control-reader", host="omarchy-normandy", kind="agent_status",
            profile="mission-control-reader", project="chaldea")])
    for status in (dict(state="running", status="disabled"), dict(state="stopped", status="enabled")):
        refused = play(tmp_path, "omarchy-normandy", roles=[role], values=values | dict(
            fixture_services={"mission-control-reader.service": status}))
        assert refused.returncode != 0, refused.stdout
        assert not (tmp_path / "reader-config").exists()
        assert not (tmp_path / "cache").exists()
    ok(play(tmp_path, "omarchy-normandy", roles=[role], values=values))
    assert not (tmp_path / "manager.json").exists()
    tasks = [{"ansible.builtin.include_role": dict(name=role)},
             {"ansible.builtin.include_role": dict(name=role, tasks_from="activate")}]
    failed = play(tmp_path, "omarchy-normandy", tasks=tasks, values=values | dict(mission_control_activate=True))
    assert failed.returncode != 0
    assert not (tmp_path / "manager.json").exists()
    values |= dict(mission_control_activate=True, mission_control_system_verification=dict(rc=0))
    ok(play(tmp_path, "omarchy-normandy", tasks=tasks, values=values))
    # A warm config change must survive the include and request a restart.
    config = tmp_path / "reader-config/reader.json"
    config.write_text("{}")
    unit = tmp_path / "units/mission-control-reader.service"
    installed_unit = unit.read_bytes()
    unit.write_text("[Service]\n")
    protected = [config, unit, tmp_path / "manager.json", tmp_path / "manager.events"]
    before = [(p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in protected]
    checked = play(tmp_path, "omarchy-normandy", tasks=tasks, values=values, check=True)
    ok(checked)
    assert "allowedSourceIds" in checked.stdout and "NoNewPrivileges=no" in checked.stdout
    assert "after:" in checked.stdout and "changed=0" not in checked.stdout
    assert before == [(p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in protected]
    unit.write_bytes(installed_unit)
    ok(play(tmp_path, "omarchy-normandy", tasks=tasks, values=values))
    events = [json.loads(line) for line in (tmp_path / "manager.events").read_text().splitlines()]
    assert events[-1]["state"] == "restarted"
    assert events[-1]["daemon_reload"] is False
    again = play(tmp_path, "omarchy-normandy", tasks=tasks, values=values)
    ok(again)
    assert "changed=0" in again.stdout
    (tmp_path / "units/mission-control-reader.service").write_text("[Service]\n")
    ok(play(tmp_path, "omarchy-normandy", tasks=tasks, values=values))
    events = [json.loads(line) for line in (tmp_path / "manager.events").read_text().splitlines()]
    assert events[-1]["state"] == "restarted" and events[-1]["daemon_reload"] is True
