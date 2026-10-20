"""Source/render contracts; these tests do not qualify systemd/kernel behavior."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from jinja2 import Environment, FileSystemLoader
import pytest
import yaml

from test_chaldea_client import ROOT, fixture, run, safe

ROLE = ROOT / "roles/chaldea_client"
TEMPLATES = ROLE / "templates"


def context():
    return {"ansible_facts": {"user_uid": 1001, "user_gid": 1001},
            "fleet_home": "/home/fleet", "chaldea_client_root": "/home/fleet/.local/share/chaldea",
            "chaldea_client_waits_resolved_runtime": "/home/fleet/.local/share/chaldea/releases/client-v9.0.0",
            "chaldea_node_version": "26.12.0", "chaldea_client_session_policy_enabled": True,
            "chaldea_client_session_policy_path": "/etc/chaldea/sessions/policy.json",
            "chaldea_client_waits_environment": "fixture"}


def render(name):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), trim_blocks=True,
                      keep_trailing_newline=True)
    env.filters.update({"bool": bool, "to_json": json.dumps})
    return env.get_template(name).render(context())


def play(tmp_path, variables, tasks):
    safe(tmp_path)
    path = tmp_path / "guards.yml"
    path.write_text(yaml.safe_dump([{
        "name": "Waits contracts in scratch", "hosts": "localhost", "connection": "local",
        "gather_facts": False, "vars": variables, "tasks": tasks,
    }]))
    return subprocess.run(["ansible-playbook", "-i", "localhost,", str(path)],
                          cwd=ROOT, capture_output=True, text=True)




def test_preflight_facts_exclude_environment(tmp_path):
    safe(tmp_path)
    source = yaml.safe_load((ROOT / "playbooks/chaldea-waits-preflight.yml").read_text())[0]
    path = tmp_path / "facts.yml"
    path.write_text(yaml.safe_dump([{
        "name": "Qualify only public identity facts in scratch",
        "hosts": "localhost", "connection": "local", "gather_facts": True,
        "gather_subset": source["gather_subset"],
        "tasks": [{"name": "Require identity without environment collection",
                   "ansible.builtin.assert": {"that": [
                       "ansible_facts.env is not defined",
                       "ansible_facts.hostname is defined",
                       "ansible_facts.user_uid is defined",
                       "ansible_facts.user_gid is defined",
                   ], "quiet": True}}],
    }]))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("template_name", ["chaldea-waits-system.service.j2", "chaldea-waits-preflight.service.j2"])
def test_system_template_bytes_match_ansible(tmp_path, template_name):
    module_path = tmp_path / "module.service"
    lookup_path = tmp_path / "lookup.service"
    template = str(TEMPLATES / template_name)
    result = play(tmp_path, context(), [
        {"name": "Render the real module bytes", "ansible.builtin.template": {
            "src": template, "dest": str(module_path), "mode": "0600"}},
        {"name": "Record the exact ownership lookup bytes", "ansible.builtin.copy": {
            "content": "{{ lookup('ansible.builtin.template', '" + template + "') }}",
            "dest": str(lookup_path), "mode": "0600"}},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    module = module_path.read_text()
    lookup = lookup_path.read_text()
    assert module == lookup, "module versus lookup:\n" + repr(module) + "\n" + repr(lookup)
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in module.splitlines()
    assert ("\nExecStartPre=" if "system.service" in template_name else "\nExecStart=") in module


def test_default_user_and_restrictive_system_paths():
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert defaults["chaldea_client_waits_service_mode"] == "user"
    assert defaults["chaldea_client_waits_enabled"] is False
    old = (TEMPLATES / "chaldea-waits.service.j2").read_text()
    assert "ReadWritePaths=%h/.local/state/chaldea %h/.cache/chaldea-waits %t" in old
    daemon = render("chaldea-waits-system.service.j2")
    probe = render("chaldea-waits-preflight.service.j2")
    sandbox = render("chaldea-waits-system-sandbox.j2")
    assert sandbox in daemon and sandbox in probe
    for text in [daemon, probe]:
        assert "%h" not in text and "%t" not in text
        assert "User=1001\nGroup=1001" in text
        assert "PrivateUsers=true" in text and "NoNewPrivileges=true" in text
        assert "ProtectSystem=strict" in text and "ProtectHome=read-only" in text
        assert "RuntimeDirectoryMode=0700" in text
        assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in text
        assert "ReadWritePaths=/home/fleet/.local/state/chaldea /run/chaldea-waits-1001\n" in text
        assert "Environment=HOME=/home/fleet" in text
        assert "StateDirectory=" not in text
    assert daemon.index("waits-policy-check.mjs") < daemon.index("\nExecStart=")
    assert "waits serve" not in probe and "waits-namespace-check.mjs" in probe


@pytest.mark.parametrize("mode", ["user", "invalid"])
def test_incompatible_policy_refused_before_mutation(tmp_path, monkeypatch, mode):
    variables = fixture(tmp_path, monkeypatch)
    variables |= {"chaldea_client_session_policy_enabled": True,
                  "chaldea_client_waits_service_mode": mode, "chaldea_client_waits_enabled": True}
    result = run(tmp_path, variables)
    assert result.returncode != 0
    assert "Protected sessions require explicit system waits mode" in result.stdout
    assert "Inspect operator-provisioned" not in result.stdout
    assert not (Path.home() / ".config").exists()
    assert not (Path.home() / ".local").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]


def owners():
    rows = []
    for scope, path, template in [
        ("--user", "/home/fleet/.config/systemd/user/chaldea-waits.service", "chaldea-waits.service.j2"),
        ("--system", "/etc/systemd/system/chaldea-waits.service", "chaldea-waits-system.service.j2"),
    ]:
        command = {"item": {"scope": scope, "path": path, "template": str(TEMPLATES / template)},
                   "stdout_lines": ["DropInPaths=", "ActiveState=inactive", "UnitFileState=disabled",
                                    "LoadState=loaded", "FragmentPath=" + path]}
        rows.append({"item": command, "stat": {"exists": True, "isreg": True, "islnk": False,
                     "uid": 0 if scope == "--system" else 1001, "mode": "0644", "nlink": 1,
                     "checksum": ("{{ chaldea_waits_rendered_system.stat.checksum }}" if scope == "--system"
                                  else hashlib.sha256(render(template).encode()).hexdigest())}})
    return rows


@pytest.mark.parametrize("case", ["owned", "absent", "masked", "foreign", "dropin", "alias",
                                  "unknown", "dual-active", "wrong-owner", "bad-state"])
def test_real_ansible_ownership_gate(tmp_path, case):
    rows = owners()
    if case == "absent":
        for row in rows:
            row["stat"] = {"exists": False}
            row["item"]["stdout_lines"] = ["DropInPaths=", "ActiveState=inactive",
                                            "LoadState=not-found", "UnitFileState="]
    elif case == "masked":
        rows[0]["stat"] = {"exists": True, "islnk": True, "lnk_target": "/dev/null"}
        rows[0]["item"]["stdout_lines"] = ["DropInPaths=", "ActiveState=inactive",
                                           "LoadState=masked", "UnitFileState=masked"]
    elif case == "foreign":
        rows[0]["stat"]["checksum"] = "foreign"
    elif case == "dropin":
        rows[0]["item"]["stdout_lines"][0] = "DropInPaths=/foreign.conf"
    elif case == "alias":
        rows[0]["item"]["stdout_lines"][-1] = "FragmentPath=/foreign.service"
    elif case == "unknown":
        rows[0]["item"]["stdout_lines"] = []
    elif case == "dual-active":
        for row in rows:
            row["item"]["stdout_lines"][1] = "ActiveState=active"
    elif case == "wrong-owner":
        rows[1]["stat"]["uid"] = 1001
    elif case == "bad-state":
        rows[0]["item"]["stdout_lines"][2] = "UnitFileState=indirect"
    variables = context() | {
        "chaldea_client_waits_owner_files": {"results": rows},
        "chaldea_client_waits_owners": {"results": [r["item"] for r in rows]},
    }
    assertion = yaml.safe_load((ROLE / "tasks/waits-owner.yml").read_text())[-1]
    # The exact on-disk module bytes are the admission fixture. The guard
    # independently compares them with its real Ansible template lookup.
    unit = tmp_path / "owned-system.service"
    result = play(tmp_path, variables, [
        {"name": "Render the actual owned system definition", "ansible.builtin.template": {
            "src": str(TEMPLATES / "chaldea-waits-system.service.j2"), "dest": str(unit), "mode": "0644"}},
        {"name": "Hash its actual bytes", "ansible.builtin.stat": {
            "path": str(unit), "checksum_algorithm": "sha256"}, "register": "chaldea_waits_rendered_system"},
        assertion,
    ])
    assert (result.returncode == 0) == (case in ["owned", "absent", "masked"]), result.stdout + result.stderr


@pytest.mark.parametrize("case", ["root-self", "only-self", "identity", "unsafe-ancestor"])
def test_namespace_probe_exact_maps_and_public_reads(tmp_path, case):
    script = render("waits-namespace-check.mjs.j2")
    # Replace the single fs import with a strict read allowlist. Any access to
    # credentials, configuration or policy content fails this executable test.
    script = script.replace(
        "import { readFileSync, lstatSync, accessSync, constants } from 'node:fs';",
        """const constants = {R_OK: 4, X_OK: 1};
const readFileSync = path => {
  if (!['/proc/self/uid_map', '/proc/self/gid_map'].includes(path)) throw Error('unexpected read');
  return MAP;
};
const allowed = ['/', '/etc', '/etc/chaldea', '/etc/chaldea/sessions'];
const lstatSync = path => {
  if (!allowed.includes(path)) throw Error('unexpected stat');
  return {isDirectory: () => true, isSymbolicLink: () => false, uid: 0, gid: 0, mode: MODE};
};
const accessSync = path => {if (!allowed.includes(path)) throw Error('unexpected access');};
process.getuid = () => 1001;
process.getgid = () => 1001;""")
    maps = {"root-self": "0 0 1\n1001 1001 1", "only-self": "1001 1001 1",
            "identity": "0 0 65536", "unsafe-ancestor": "0 0 1\n1001 1001 1"}
    path = tmp_path / "probe.mjs"
    path.write_text("const MAP = " + json.dumps(maps[case]) + ";\nconst MODE = " +
                    ("0o777" if case == "unsafe-ancestor" else "0o755") + ";\n" + script)
    result = subprocess.run(["node", str(path)], capture_output=True, text=True)
    assert (result.returncode == 0) == (case == "root-self"), result.stdout + result.stderr
    if case == "root-self":
        assert json.loads(result.stdout)["maps"]["uid"] == [[0, 0, 1], [1001, 1001, 1]]




@pytest.mark.parametrize("case", [
    "current", "explicit", "runtime-symlink-escape", "entrypoint-symlink-escape",
    "missing-runtime", "missing-entrypoint", "runtime-file", "entrypoint-directory",
    "writable-directory", "writable-entrypoint", "unsafe-canonical-path",
])
def test_existing_runtime_resolution_and_safety(tmp_path, case):
    safe(tmp_path)
    root = Path.home() / ".local/share/chaldea"
    installed = root / "releases/client-v9.0.0"
    binary = installed / "bin/chaldea"
    loader = installed / "src/session/policy.ts"
    for path in [binary, loader]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// public fixture entrypoint\n")
        path.chmod(0o644)
    current = root / "current"
    current.symlink_to(installed, target_is_directory=True)
    selected = current
    outside = Path.home() / "outside"
    outside.mkdir()
    if case == "explicit":
        selected = installed
    elif case == "runtime-symlink-escape":
        for name in ["bin/chaldea", "src/session/policy.ts"]:
            path = outside / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// outside fixture\n")
        current.unlink()
        current.symlink_to(outside, target_is_directory=True)
    elif case == "unsafe-canonical-path":
        unsafe = root / "with space"
        for name in ["bin/chaldea", "src/session/policy.ts"]:
            path = unsafe / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// unsafe path fixture\n")
        current.unlink()
        current.symlink_to(unsafe, target_is_directory=True)
    elif case == "entrypoint-symlink-escape":
        foreign = outside / "entrypoint"
        foreign.write_text("// outside fixture\n")
        binary.unlink()
        binary.symlink_to(foreign)
    elif case == "missing-runtime":
        selected = root / "missing"
    elif case == "missing-entrypoint":
        binary.unlink()
    elif case == "runtime-file":
        selected = root / "file"
        selected.write_text("not a directory")
    elif case == "entrypoint-directory":
        binary.unlink()
        binary.mkdir()
    elif case == "writable-directory":
        installed.parent.chmod(0o777)
    elif case == "writable-entrypoint":
        binary.chmod(0o666)
    variables = {
        "ansible_facts": {"user_uid": os.getuid()},
        "chaldea_client_root": str(root), "chaldea_client_waits_runtime_root": str(selected),
        "chaldea_client_session_policy_enabled": True,
    }
    canonical = yaml.safe_load((ROLE / "tasks/waits-system-validate.yml").read_text())
    start = next(i for i, task in enumerate(canonical)
                 if task["name"] == "Resolve the existing waits runtime and its required entrypoints")
    tasks = canonical[start:] + [{"name": "Require the measured canonical runtime",
                                  "ansible.builtin.assert": {"that": [
                                      "chaldea_client_waits_resolved_runtime == " + repr(str(installed))]}}]
    result = play(tmp_path, variables, tasks)
    assert (result.returncode == 0) == (case in ["current", "explicit"]), result.stdout + result.stderr


def test_foreign_runtime_owner_refused(tmp_path):
    canonical = yaml.safe_load((ROLE / "tasks/waits-system-validate.yml").read_text())
    assertion = canonical[-1]
    variables = {
        "ansible_facts": {"user_uid": 1001},
        "chaldea_client_waits_runtime_paths": {"stdout_lines": ["/root", "/root/client", "/root/client/bin/chaldea"]},
        "chaldea_client_waits_runtime_files": {"results": [{
            "item": "/root/client/bin/chaldea",
            "stat": {"exists": True, "islnk": False, "isreg": True, "nlink": 1,
                     "uid": 23456, "mode": "0644", "readable": True},
        }]},
    }
    result = play(tmp_path, variables, [assertion])
    assert result.returncode != 0 and "foreign-owned" in result.stdout, result.stdout + result.stderr


def test_preflight_and_activation_order():
    preflight = (ROLE / "tasks/waits-preflight.yml").read_text()
    probe = render("waits-namespace-check.mjs.j2")
    assert probe.count("import ") == 1 and "from 'node:fs'" in probe
    for forbidden in ["waits.json", "policy.json", "authentik", "sops", "fetch(", "node:net",
                      "child_process", "loadSessionPolicy"]:
        assert forbidden not in probe
    assert "session-policy.yml" not in preflight and "waits-system.yml" not in preflight
    activation = (ROLE / "tasks/waits-system.yml").read_text()
    assert activation.index("waits-owner.yml") < activation.index("waits-preflight.yml")
    assert activation.index("waits-preflight.yml") < activation.index("Inspect waits tokens")
    assert activation.index("state: stopped") < activation.index("state: link") < activation.index("Start the sole")
    assert activation.index("ActiveState=inactive") < activation.index("Render waits configuration")
    assert "get_url" not in activation and "current\"" not in activation and "previous\"" not in activation
    loader = render("waits-policy-check.mjs.j2")
    assert "loadSessionPolicy(" in loader and "owners:" not in loader and "stopAt:" not in loader
