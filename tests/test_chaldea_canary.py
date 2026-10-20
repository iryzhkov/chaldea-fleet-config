"""Bounded service and public gate contracts. No host/systemd qualification."""
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader
import pytest
import yaml

from test_chaldea_client import safe
from test_chaldea_session_policy import policy_variables, protected_tree, PRESET
from test_chaldea_waits_system import ROLE, TEMPLATES, context, play

PERSISTENT = "# Managed by chaldea-fleet-config. System waits owner.\n[Unit]\nDescription=Chaldea durable waits and decision inbox\nAfter=network.target\nStartLimitIntervalSec=0\n\n[Service]\nType=simple\n{% include 'chaldea-waits-system-sandbox.j2' %}\n\nExecStartPre={{ fleet_home }}/.local/share/mise/installs/node/{{ chaldea_node_version }}/bin/node {{ fleet_home }}/.config/chaldea/waits-namespace-check.mjs\n{% if chaldea_client_session_policy_enabled | bool %}\nExecStartPre={{ fleet_home }}/.local/share/mise/installs/node/{{ chaldea_node_version }}/bin/node {{ fleet_home }}/.config/chaldea/waits-policy-check.mjs\n{% endif %}\nExecStart={{ fleet_home }}/.local/share/mise/installs/node/{{ chaldea_node_version }}/bin/node {{ chaldea_client_waits_resolved_runtime }}/bin/chaldea waits serve --config {{ fleet_home }}/.config/chaldea/waits.json\nRestart=on-failure\nRestartSec=5\nStandardOutput=null\nStandardError=journal\n\n[Install]\nWantedBy=multi-user.target\n"


def render(name, variables):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), trim_blocks=True,
                      keep_trailing_newline=True)
    env.filters.update(bool=bool, to_json=json.dumps)
    return env.get_template(name).render(variables)


def deadline(seconds=300):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def helper(tmp_path, **overrides):
    safe(tmp_path)
    variables = context() | {"fleet_home": str(Path.home()), "chaldea_client_waits_deadline": deadline()} | overrides
    state = Path.home() / ".local/state/chaldea"
    state.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "deadline.mjs"
    script.write_text(render("waits-deadline.mjs.j2", variables))
    return script, state / "waits-bounded-starts.json", variables


def node(script, action):
    return subprocess.run(["node", str(script), action], capture_output=True, text=True)


@pytest.mark.parametrize("value", ["expired", "far", "2026-02-30T01:00:00Z", "2026-10-20", "2026-10-20T12:00:00+00:00"])
def test_deadline_refuses_before_state_write(tmp_path, value):
    value = deadline(-1) if value == "expired" else deadline(2800) if value == "far" else value
    script, record, _ = helper(tmp_path, chaldea_client_waits_deadline=value)
    for action in ["--check", "--reserve", "--start", "--authorize-status-read"]:
        result = node(script, action)
        assert result.returncode != 0, result.stdout + result.stderr
        assert not record.exists()


def test_actual_clock_convergence_and_consumed_restart(tmp_path):
    script, record, variables = helper(tmp_path)
    first = node(script, "--check")
    second = node(script, "--check")
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert not record.exists()
    assert node(script, "--reserve").returncode == 0
    assert json.loads(record.read_text())["starts"] == 0
    assert 0 < json.loads(second.stdout)["remainingSeconds"] <= json.loads(first.stdout)["remainingSeconds"]
    # Capture only execve, preserving deadline/state code and its real filesystem operations.
    original = script.read_text()
    script.write_text("process.execve = (path, args) => { console.log(JSON.stringify({path, args})); process.exit(0); };\n" + original)
    launch = node(script, "--start")
    assert launch.returncode == 0, launch.stderr
    execution = json.loads(launch.stdout)
    assert execution["path"] == "/usr/bin/timeout"
    assert "--kill-after=5s" in execution["args"]
    assert 0 < int(execution["args"][3][:-1]) <= 290
    assert json.loads(record.read_text())["starts"] == 1
    assert node(script, "--start").returncode != 0
    assert node(script, "--authorize-status-read").returncode == 0
    assert node(script, "--start").returncode == 0
    assert json.loads(record.read_text())["starts"] == 2
    assert node(script, "--start").returncode != 0
    assert node(script, "--authorize-status-read").returncode != 0
    # Changing the deadline never renews a consumed launch.
    helper(tmp_path, chaldea_client_waits_deadline=deadline(600))
    assert node(script, "--check").returncode != 0


def test_expired_restart_and_corrupt_record_fail_closed(tmp_path):
    script, record, _ = helper(tmp_path)
    record.write_text("{")
    record.chmod(0o600)
    assert node(script, "--check").returncode != 0
    record.unlink()
    script.write_text("Date.now = () => Number.MAX_SAFE_INTEGER;\n" + script.read_text())
    assert node(script, "--start").returncode != 0
    assert not record.exists()


def test_finite_unit_and_persistent_bytes():
    variables = context()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), trim_blocks=True, keep_trailing_newline=True)
    env.filters.update(bool=bool, to_json=json.dumps)
    persistent = render("chaldea-waits-system.service.j2", variables)
    assert persistent == env.from_string(PERSISTENT).render(variables)
    bounded = render("chaldea-waits-system.service.j2", variables | {"chaldea_client_waits_deadline": deadline()})
    assert "Restart=no\nRuntimeMaxSec=2700s\n" in bounded
    assert "TimeoutStopSec=5s\nKillMode=control-group\n" in bounded
    assert "[Install]" not in bounded and "WantedBy=" not in bounded
    assert "waits-deadline.mjs --start" in bounded
    assert "waits-deadline.mjs --namespace-check" in bounded
    assert "waits-deadline.mjs --policy-check" in bounded
    sandbox = render("chaldea-waits-system-sandbox.j2", variables)
    assert sandbox in bounded
    gate = render("chaldea-waits-policy-gate.service.j2", variables)
    assert sandbox in gate and "waits serve" not in gate and "[Install]" not in gate
    assert "waits-policy-check.mjs" in gate
    assert "RemainAfterExit=yes" in gate


@pytest.mark.skipif(os.getuid() != 0, reason="requires real UID 0 ownership; retained agent-a root-case evidence is required")
@pytest.mark.parametrize("unsafe", [False, True])
def test_public_render_without_secret_and_without_credential_tasks(tmp_path, monkeypatch, unsafe):
    variables = policy_variables(tmp_path, monkeypatch)
    extra = protected_tree(tmp_path)
    # Run with actual UID 0 in agent-a; ordinary CI explicitly skips these two cases.
    extra["chaldea_client_session_policy_owner"] = "0"
    extra["chaldea_client_session_policy_owner_uid"] = 0
    path = Path(extra["chaldea_client_session_policy_path"])
    if unsafe:
        path.parent.parent.parent.chmod(0o777)
    secret = Path(variables["chaldea_client_session_enrollments"][PRESET]["secretFile"])
    assert not secret.exists()
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    tasks = [{"name": "Public-only policy slice", "ansible.builtin.include_role": {
        "name": "chaldea_client", "tasks_from": name, "public": True}} for name in
        ["session-policy-public-validate", "session-policy-public-render"]]
    # Extra vars override only the test's scratch destination; test the production guard separately.
    playfile = tmp_path / "public.yml"
    playfile.write_text(yaml.safe_dump([{"name": "Public policy in scratch", "hosts": "localhost",
        "connection": "local", "gather_facts": False, "vars": defaults | variables, "tasks": tasks}]))
    extra_file = tmp_path / "extra.json"
    extra_file.write_text(json.dumps(extra))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROLE.parent))
    command = ["ansible-playbook", "-i", "localhost,", str(playfile), "-e", "@" + str(extra_file)]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == (not unsafe), result.stdout + result.stderr
    assert "Inspect operator-provisioned" not in result.stdout
    assert "Inspect waits tokens" not in result.stdout
    assert not secret.exists()
    if not unsafe:
        assert json.loads(path.read_text())["enrollments"][PRESET]["secretFile"] == str(secret)
        repeated = subprocess.run(command, env=env, capture_output=True, text=True)
        assert repeated.returncode == 0 and "changed=0" in repeated.stdout, repeated.stdout + repeated.stderr


def test_gate_refuses_fixture_owner_before_any_following_task(tmp_path):
    gate = yaml.safe_load((ROLE / "tasks/session-policy-gate.yml").read_text())
    variables = context() | {
        "chaldea_client_session_policy_root": "/", "chaldea_client_session_policy_owner": "fixture",
        "chaldea_client_session_policy_owner_uid": 0, "chaldea_client_session_policy_become": True,
    }
    result = play(tmp_path, variables, [gate[0], {"name": "ENROLLMENT_MUST_NOT_RUN",
        "ansible.builtin.fail": {"msg": "credential action reached"}}])
    assert result.returncode != 0
    assert "ENROLLMENT_MUST_NOT_RUN" not in result.stdout


def test_gate_reuses_validator_and_loader_without_credential_imports():
    source = (ROLE / "tasks/session-policy-gate.yml").read_text()
    assert "session-policy-public-validate.yml" in source
    assert "session-policy-public-render.yml" in source
    assert "session-policy-credentials" not in source and "session-policy.yml" not in source
    assert "waits-system.yml" not in source
    assert "community.sops" not in source and "get_url:" not in source
    loader = render("waits-policy-check.mjs.j2", context())
    assert "loadSessionPolicy(" in loader and "owners:" not in loader and "stopAt:" not in loader
    assert "public_files:" in source and "invocation_id:" in source


@pytest.mark.parametrize("starts,active,restart,allowed", [
    (0, False, False, True), (1, True, False, True), (1, False, False, False),
    (1, False, True, True), (1, True, True, False), (2, False, True, False),
])
def test_bounded_ansible_lifecycle_gate(tmp_path, starts, active, restart, allowed):
    canonical = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
    assertion = next(t for t in canonical if t["name"].startswith("Refuse implicit bounded relaunch"))
    variables = {"chaldea_client_waits_deadline": deadline(),
        "chaldea_client_waits_status_read_restart": restart,
        "chaldea_client_waits_bounded_state": {"starts": starts},
        "chaldea_client_waits_owners": {"results": [{}, {
            "stdout_lines": ["ActiveState=" + ("active" if active else "inactive")]}]}}
    result = play(tmp_path, variables, [assertion])
    assert (result.returncode == 0) == allowed, result.stdout + result.stderr


def test_loader_refusal_prevents_evidence_and_enrollment(tmp_path):
    gate = yaml.safe_load((ROLE / "tasks/session-policy-gate.yml").read_text())
    assertion = next(t for t in gate if t["name"].startswith("Require actual maintained loader success"))
    result = play(tmp_path, {"ansible_check_mode": False,
        "chaldea_client_policy_gate_result": {"status": {"Result": "exit-code", "ExecMainStatus": "1"}}},
        [assertion, {"name": "ENROLLMENT_MUST_NOT_RUN",
                     "ansible.builtin.fail": {"msg": "enrollment reached"}}])
    assert result.returncode != 0 and "ENROLLMENT_MUST_NOT_RUN" not in result.stdout


def test_launcher_executes_timeout_with_exact_staged_argv(tmp_path):
    runtime = Path.home() / ".local/share/chaldea/releases/fixture"
    script, record, variables = helper(tmp_path, chaldea_client_waits_resolved_runtime=str(runtime))
    node_path = Path.home() / ".local/share/mise/installs/node" / variables["chaldea_node_version"] / "bin/node"
    node_path.parent.mkdir(parents=True)
    actual_node = shutil.which("node")
    assert actual_node
    node_path.symlink_to(actual_node)
    cli = runtime / "bin/chaldea"
    cli.parent.mkdir(parents=True)
    cli.write_text("console.log(JSON.stringify(process.argv.slice(2)));\n")
    assert node(script, "--reserve").returncode == 0
    result = node(script, "--start")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == ["waits", "serve", "--config", str(Path.home() / ".config/chaldea/waits.json")]
    assert json.loads(record.read_text())["starts"] == 1


def test_prelaunch_interruption_keeps_original_window(tmp_path):
    script, record, variables = helper(tmp_path)
    variables |= {"chaldea_client_waits_status_read_restart": False}
    installed = Path.home() / ".config/chaldea/waits-deadline.mjs"
    unit = tmp_path / "bounded.service"
    node_path = Path.home() / ".local/share/mise/installs/node" / variables["chaldea_node_version"] / "bin/node"
    node_path.parent.mkdir(parents=True)
    executable = shutil.which("node")
    assert executable
    node_path.symlink_to(executable)
    canonical = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
    names = ["Create only private waits directories",
             "Reserve the original bounded window before installing executable files",
             "Install the fixed deadline launcher before the bounded definition",
             "Install the system waits definition"]
    chosen = [next(t for t in canonical if t["name"] == name) for name in names]
    assert [canonical.index(t) for t in chosen] == sorted(canonical.index(t) for t in chosen)
    assert canonical.index(chosen[1]) < canonical.index(next(t for t in canonical
        if t["name"] == "Prove the proposed namespace before any credential inspection"))
    checks = yaml.safe_load((ROLE / "tasks/waits-deadline.yml").read_text())

    def execute(values, interrupt=False):
        # Relocate only destinations and template lookup roots into scratch.
        import copy
        tasks = copy.deepcopy(checks + chosen)
        for task in tasks:
            task.pop("become", None)
            if "ansible.builtin.command" in task:
                args = task["ansible.builtin.command"]["argv"]
                args[3] = args[3].replace("'waits-deadline.mjs.j2'", repr(str(TEMPLATES / "waits-deadline.mjs.j2")))
            if "ansible.builtin.template" in task:
                args = task["ansible.builtin.template"]
                args["src"] = str(TEMPLATES / args["src"])
                args.pop("owner", None)
                args.pop("group", None)
                if args["dest"].startswith("/etc/"):
                    args["dest"] = str(unit)
        if interrupt:
            tasks.append({"name": "Interrupt before first launch",
                          "ansible.builtin.fail": {"msg": "prelaunch interruption"}})
        return play(tmp_path, values, tasks)

    failed = execute(variables, interrupt=True)
    assert failed.returncode != 0 and "prelaunch interruption" in failed.stdout, failed.stdout + failed.stderr
    assert json.loads(record.read_text())["starts"] == 0
    before = (record.read_bytes(), installed.read_bytes(), unit.read_bytes())
    refused = execute(variables | {"chaldea_client_waits_deadline": deadline(600)})
    assert refused.returncode != 0 and "foreign bounded waits start record" in refused.stdout, refused.stdout
    assert before == (record.read_bytes(), installed.read_bytes(), unit.read_bytes())
    recovered = execute(variables)
    assert recovered.returncode == 0 and "changed=0" in recovered.stdout, recovered.stdout + recovered.stderr
    assert before == (record.read_bytes(), installed.read_bytes(), unit.read_bytes())
    assert not json.loads(node(script, "--reserve").stdout)["reserved"]


def test_gate_captures_invocation_before_inactive_gc(tmp_path, monkeypatch):
    safe(tmp_path)
    manager = tmp_path / "manager.json"
    manager.write_text(json.dumps({"active": False, "runs": 0, "calls": []}))
    fake = tmp_path / "fake-bin/systemctl"
    fake.parent.mkdir()
    fake.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ['GATE_TEST_MANAGER'])
state = json.loads(path.read_text())
words = [w for w in sys.argv[1:] if not w.startswith('-')]
verb = words[0] if words else ''
if '--version' in sys.argv:
    print('systemd 257')
elif verb == 'show':
    active = state['active']
    print('Id=chaldea-waits-policy-gate.service\\nLoadState=loaded\\nUnitFileState=static')
    print('ActiveState=' + ('active' if active else 'inactive'))
    print('SubState=' + ('exited' if active else 'dead'))
    print('Result=success\\nExecMainStatus=0\\nDropInPaths=')
    print('FragmentPath=/etc/systemd/system/chaldea-waits-policy-gate.service')
    print('InvocationID=' + ('a' * 32 if active else ''))
elif verb in ['start', 'restart']:
    state['active'] = True
    state['runs'] += 1
elif verb == 'stop':
    state['active'] = False
elif verb == 'is-active':
    print('active' if state['active'] else 'inactive')
elif verb == 'is-enabled':
    print('static')
state['calls'].append(verb)
path.write_text(json.dumps(state))
""")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake.parent) + ":" + os.environ["PATH"])
    monkeypatch.setenv("GATE_TEST_MANAGER", str(manager))
    gate = yaml.safe_load((ROLE / "tasks/session-policy-gate.yml").read_text())
    start = next(i for i, t in enumerate(gate) if t["name"] == "Run the maintained loader in the same system sandbox")
    tasks = []
    public = Path.home() / "public-policy.json"
    public.write_text("{}")
    for original in gate[start:]:
        import copy
        task = copy.deepcopy(original)
        task.pop("become", None)
        if task["name"] == "Hash only public gate bindings":
            task["loop"] = [str(public)]
        if task["name"].startswith("Capture sanitized exact bindings"):
            fact = task["ansible.builtin.set_fact"]["chaldea_client_policy_gate_captured_evidence"]
            fact["sandbox_sha256"] = "{{ lookup('ansible.builtin.template', " + repr(str(TEMPLATES / "chaldea-waits-system-sandbox.j2")) + ") | hash('sha256') }}"
        tasks.append(task)
    receipt = tmp_path / "receipt.json"
    tasks.append({"name": "Record original evidence after GC",
                  "ansible.builtin.copy": {"content": "{{ chaldea_client_policy_gate_evidence | to_json }}",
                                          "dest": str(receipt), "mode": "0600"}})
    result = play(tmp_path, context() | {"chaldea_client_t3_home": str(Path.home() / ".t3")}, tasks)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(receipt.read_text())["invocation_id"] == "a" * 32
    state = json.loads(manager.read_text())
    assert state["runs"] == 1 and state["active"] is False
    assert state["calls"].count("stop") == 1
    # An interrupted retained gate must be refused before writes or another run.
    assertion = next(t for t in gate if t["name"].startswith("Refuse foreign loader gate definitions"))
    result = play(tmp_path, {"chaldea_client_policy_gate_manager": {
        "stdout_lines": ["DropInPaths=", "ActiveState=active"]}}, [assertion, tasks[0]])
    assert result.returncode != 0 and "retained loader gate" in result.stdout, result.stdout
    assert json.loads(manager.read_text())["runs"] == 1


def test_nonroot_ci_collection_and_explicit_skip(tmp_path):
    safe(tmp_path)
    # Exercise the non-root selection branch in a fresh interpreter. Agent-a maps
    # only UID 0 and denies nested user namespaces, so this is an identity simulation.
    source = Path(__file__).resolve()
    prefix = "import os; os.getuid = lambda: 1000; import pytest; "
    for arguments in [
        ["--collect-only", "-q", "-p", "no:cacheprovider", str(source), "-k", "public_render_without_secret"],
        ["-q", "-rs", "-p", "no:cacheprovider", str(source), "-k", "public_render_without_secret"],
    ]:
        command = prefix + "raise SystemExit(pytest.main(" + repr(arguments) + "))"
        result = subprocess.run([sys.executable, "-c", command], cwd=ROLE.parents[1],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        if "--collect-only" in arguments:
            assert "2/" in result.stdout or "2 tests collected" in result.stdout, result.stdout
        else:
            assert "2 skipped" in result.stdout
            assert "requires real UID 0 ownership" in result.stdout


@pytest.mark.parametrize("bounded", [False, True])
def test_only_persistent_mode_creates_timestamped_backups(tmp_path, bounded):
    safe(tmp_path)
    variables = yaml.safe_load((ROLE / "defaults/main.yml").read_text()) | context() | {
        "fleet_home": str(Path.home()),
        "chaldea_client_waits_deadline": deadline() if bounded else "",
    }
    config = Path.home() / ".config/chaldea/waits.json"
    config.parent.mkdir(parents=True)
    config.write_text("original public config\n")
    unit = tmp_path / "waits.service"
    unit.write_text("original public unit\n")
    canonical = yaml.safe_load((ROLE / "tasks/waits-system.yml").read_text())
    selected = []
    for name in ["Render waits configuration retaining the existing database and auth pointers",
                 "Install the system waits definition"]:
        import copy
        task = copy.deepcopy(next(t for t in canonical if t["name"] == name))
        task.pop("become", None)
        args = task["ansible.builtin.template"]
        args["src"] = str(TEMPLATES / args["src"])
        args.pop("owner", None)
        args.pop("group", None)
        if name == "Install the system waits definition":
            args["dest"] = str(unit)
        selected.append(task)
    result = play(tmp_path, variables, selected)
    assert result.returncode == 0, result.stdout + result.stderr
    for path in [config, unit]:
        backups = list(path.parent.glob(path.name + ".*"))
        assert len(backups) == (0 if bounded else 1), backups
        if backups:
            assert backups[0].read_text().startswith("original public ")
