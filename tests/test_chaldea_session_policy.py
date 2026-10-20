"""The client role's protected session policy, applied only in scratch trees.

The protected root, owner and become are fixed role variables; these tests
override them with extra vars to render into a scratch tree without root.
"""
import copy
import json
import os
import pwd
import subprocess
from pathlib import Path

import pytest
import yaml

from test_chaldea_client import ROOT, fixture, provision, safe

SECRET = "FIXTURE-APP-PASSWORD-NEVER-PRINT"
PRESET = "jocasta-projectA-reporter"
SERVICES = [{"audience": "jocasta",
             "grants": [{"resource": "project:projectA", "actions": ["get", "history", "list", "search"]}]}]


def enrollment(home):
    return {"form": "app_password",
            "issuer": "https://auth.example.test/application/o/chaldea-jocasta/",
            "tokenUrl": "https://auth.example.test/application/o/token/",
            "jwksUrl": "https://auth.example.test/application/o/chaldea-jocasta/jwks/",
            "clientId": "chaldea-jocasta-machine", "username": "chaldea-laptop-jocasta-projectA-reporter",
            "scope": "jocasta.read", "resource": "https://jocasta.example.test/mcp", "project": "projectA",
            "maxTokenSeconds": 300,
            "secretFile": str(home / ".config/chaldea/authentik" / (PRESET + ".app-password"))}


def policy_variables(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    home = Path.home()
    variables |= {
        "chaldea_client_waits_enabled": True,
        "chaldea_client_session_policy_enabled": True,
        "chaldea_client_waits_service_mode": "system",
        "chaldea_client_session_ceilings": [{"project": "projectA", "maxSeconds": 3600,
                                             "destinations": ["caller-project"], "services": SERVICES}],
        "chaldea_client_session_presets": {PRESET: {
            "instanceId": "reporter-instance", "model": "fixture-model", "runtimeMode": "approval-required",
            "interactionMode": "default", "projectId": "reporter-project", "title": "Jocasta projectA reporter",
            "prompt": "Report projectA status.", "inputs": {"scope": "status"}, "project": "projectA",
            "services": SERVICES, "maxSeconds": 1800, "delegate": False, "destinations": ["caller-project"]}},
        "chaldea_client_session_enrollments": {PRESET: enrollment(home)},
    }
    return variables


def protected_tree(tmp_path):
    """A scratch stand-in for / and /etc, owned by the test user."""
    safe(tmp_path)
    root = tmp_path / "protected"
    (root / "etc").mkdir(parents=True)
    root.chmod(0o755)
    (root / "etc").chmod(0o755)
    return {"chaldea_client_session_policy_root": str(root),
            "chaldea_client_session_policy_path": str(root / "etc/chaldea/sessions/policy.json"),
            "chaldea_client_session_policy_owner": pwd.getpwuid(os.getuid()).pw_name,
            "chaldea_client_session_policy_owner_uid": os.getuid(),
            "chaldea_client_session_policy_become": False}


def provision_app_password(content=SECRET, mode=0o600):
    home = Path.home()
    safe(home)
    directory = home / ".config/chaldea/authentik"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    path = directory / (PRESET + ".app-password")
    path.write_text(content)
    path.chmod(mode)
    return path


def run(base, variables, extra, check=False):
    safe(base)
    play = base / "policy.yml"
    play.write_text(yaml.safe_dump([{"name": "Client role with a session policy in scratch", "hosts": "localhost",
                                    "connection": "local", "gather_facts": False,
                                    "vars": yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text()) | variables,
                                    "tasks": [
                                        {"name": "Exercise the policy writer independently of service activation",
                                         "ansible.builtin.include_role": {"name": "chaldea_client", "tasks_from": "session-policy", "public": True},
                                         "when": "chaldea_client_session_policy_enabled | bool"},
                                        {"name": "Render its waits policy pointer",
                                         "ansible.builtin.template": {"src": str(ROOT / "roles/chaldea_client/templates/waits.json.j2"),
                                                                    "dest": "{{ fleet_home }}/.config/chaldea/waits.json",
                                                                    "mode": "0600"}}]}]))
    extra_file = base / "protected.json"
    extra_file.write_text(json.dumps(extra))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"),
               ANSIBLE_LOCAL_TEMP=str(base / "ansible-local"), ANSIBLE_REMOTE_TEMP=str(base / "ansible-remote"))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play), "-e", "@" + str(extra_file),
                             *(["--check", "--diff"] if check else [])],
                            env=env, cwd=ROOT, capture_output=True, text=True)
    assert SECRET not in result.stdout + result.stderr
    assert "FIXTURE-SECRET-NEVER-PRINT" not in result.stdout + result.stderr
    return result


def ok(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_disabled_policy_renders_nothing_and_leaves_waits_config_alone(tmp_path, monkeypatch):
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    assert defaults["chaldea_client_session_policy_enabled"] is False
    assert defaults["chaldea_client_session_enrollments"] == {}
    fixed = yaml.safe_load((ROOT / "roles/chaldea_client/vars/main.yml").read_text())
    assert fixed["chaldea_client_session_policy_path"] == "/etc/chaldea/sessions/policy.json"
    assert (fixed["chaldea_client_session_policy_owner"], fixed["chaldea_client_session_policy_owner_uid"]) == ("root", 0)
    variables = fixture(tmp_path, monkeypatch) | {"chaldea_client_waits_enabled": True}
    provision()
    extra = protected_tree(tmp_path)
    ok(run(tmp_path, variables, extra))
    waits = json.loads((Path.home() / ".config/chaldea/waits.json").read_text())
    assert "sessionPolicy" not in waits
    assert not (tmp_path / "protected/etc/chaldea").exists()


def test_policy_is_rendered_protected_public_and_idempotent(tmp_path, monkeypatch):
    variables = policy_variables(tmp_path, monkeypatch)
    provision()
    provision_app_password()
    extra = protected_tree(tmp_path)
    check = run(tmp_path, variables, extra, check=True)
    ok(check)
    path = Path(extra["chaldea_client_session_policy_path"])
    assert not path.exists()
    ok(run(tmp_path, variables, extra))
    text = path.read_text()
    assert SECRET not in text
    assert json.loads(text) == {
        "version": 1, "environment": "fixture-environment",
        "ceilings": variables["chaldea_client_session_ceilings"],
        "presets": variables["chaldea_client_session_presets"],
        "enrollments": variables["chaldea_client_session_enrollments"]}
    st = path.lstat()
    assert (st.st_mode & 0o777, st.st_uid, st.st_nlink) == (0o644, os.getuid(), 1)
    for directory in (path.parent, path.parent.parent):
        assert directory.stat().st_mode & 0o777 == 0o755
    waits = json.loads((Path.home() / ".config/chaldea/waits.json").read_text())
    assert waits["sessionPolicy"] == str(path)
    repeated = run(tmp_path, variables, extra)
    ok(repeated)
    assert "changed=0" in repeated.stdout, repeated.stdout


def test_policy_without_enrollments_has_no_enrollments_key(tmp_path, monkeypatch):
    variables = policy_variables(tmp_path, monkeypatch) | {"chaldea_client_session_enrollments": {}}
    provision()
    extra = protected_tree(tmp_path)
    ok(run(tmp_path, variables, extra))
    policy = json.loads(Path(extra["chaldea_client_session_policy_path"]).read_text())
    assert sorted(policy) == ["ceilings", "environment", "presets", "version"]


def mutate(change):
    def apply(variables):
        enroll = variables["chaldea_client_session_enrollments"][PRESET]
        preset = variables["chaldea_client_session_presets"][PRESET]
        change(enroll, preset, variables)
    return apply


REFUSALS = {
    "other form": (mutate(lambda e, p, v: e.update(form="client_secret")), "Enrollment"),
    "extra scope": (mutate(lambda e, p, v: e.update(scope="jocasta.read jocasta.write")), "Enrollment"),
    "long tokens": (mutate(lambda e, p, v: e.update(maxTokenSeconds=3600)), "Enrollment"),
    "plain http issuer": (mutate(lambda e, p, v: e.update(issuer="http://auth.example.test/application/o/chaldea-jocasta/")), "Enrollment"),
    "token url elsewhere": (mutate(lambda e, p, v: e.update(tokenUrl="https://other.example.test/application/o/token/")), "Enrollment"),
    "jwks query": (mutate(lambda e, p, v: e.update(jwksUrl=e["jwksUrl"] + "?kid=x")), "Enrollment"),
    "resource userinfo": (mutate(lambda e, p, v: e.update(resource="https://u@jocasta.example.test/mcp")), "Enrollment"),
    "default port": (mutate(lambda e, p, v: e.update(resource="https://jocasta.example.test:443/mcp")), "Enrollment"),
    "other project": (mutate(lambda e, p, v: e.update(project="projectB")), "Enrollment"),
    "wider grant": (mutate(lambda e, p, v: p.update(services=[{"audience": "jocasta", "grants": [
        {"resource": "project:projectA", "actions": ["get"]}, {"resource": "project:projectB", "actions": ["get"]}]}])),
        "Enrollment"),
    "secret elsewhere": (mutate(lambda e, p, v: e.update(secretFile="/etc/shadow")), "Enrollment"),
    "client secret field": (mutate(lambda e, p, v: e.update(clientSecret="x")), "Enrollment"),
    "delegating preset": (mutate(lambda e, p, v: p.update(delegate=True)), "delegate: false"),
    "unknown preset": (mutate(lambda e, p, v: v["chaldea_client_session_enrollments"].update(
        other=copy.deepcopy(e))), "enrollments only for declared presets"),
    "waits off": (mutate(lambda e, p, v: v.update(chaldea_client_waits_enabled=False)), "waits enabled"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_unsupported_policy_is_refused_before_any_write(tmp_path, monkeypatch, case):
    change, message = REFUSALS[case]
    variables = policy_variables(tmp_path, monkeypatch)
    change(variables)
    provision()
    provision_app_password()
    extra = protected_tree(tmp_path)
    result = run(tmp_path, variables, extra)
    assert result.returncode != 0
    assert message in result.stdout, result.stdout
    assert not (tmp_path / "protected/etc/chaldea").exists()
    assert not (Path.home() / ".local/share/chaldea").exists()
    assert not (Path.home() / ".config/chaldea/waits.json").exists()


@pytest.mark.parametrize("failure", ["missing", "mode", "empty", "symlink", "directory"])
def test_unsafe_app_password_is_refused_by_stat_only(tmp_path, monkeypatch, failure):
    variables = policy_variables(tmp_path, monkeypatch)
    provision()
    path = provision_app_password(content="" if failure == "empty" else SECRET,
                                  mode=0o644 if failure == "mode" else 0o600)
    if failure == "missing":
        path.unlink()
    elif failure == "symlink":
        target = Path.home() / "elsewhere"
        target.write_text(SECRET)
        target.chmod(0o600)
        path.unlink()
        path.symlink_to(target)
    elif failure == "directory":
        path.parent.chmod(0o755)
    result = run(tmp_path, variables, protected_tree(tmp_path))
    assert result.returncode != 0
    assert "Refusing the session policy" in result.stdout, result.stdout
    assert not (tmp_path / "protected/etc/chaldea").exists()


@pytest.mark.parametrize("failure", ["writable", "linked", "hard link"])
def test_unprotected_policy_path_is_refused(tmp_path, monkeypatch, failure):
    variables = policy_variables(tmp_path, monkeypatch)
    provision()
    provision_app_password()
    extra = protected_tree(tmp_path)
    etc = tmp_path / "protected/etc"
    if failure == "writable":
        etc.chmod(0o775)
    else:
        sessions = etc / "chaldea/sessions"
        sessions.mkdir(parents=True)
        (etc / "chaldea").chmod(0o755)
        sessions.chmod(0o755)
        other = tmp_path / "other.json"
        other.write_text("{}")
        if failure == "linked":
            (sessions / "policy.json").symlink_to(other)
        else:
            os.link(other, sessions / "policy.json")
    result = run(tmp_path, variables, extra)
    assert result.returncode != 0
    assert "writable by no one else" in result.stdout, result.stdout
    if failure != "writable":
        assert (tmp_path / "other.json").read_text() == "{}"


# New service profiles use the same flat public grant in all three locations.
GRANTS = {
    "ov": {"audience": "ov", "scope": "ov.read",
           "ov_namespaces": ["viking://resources/namespaceA/child", "viking://resources/namespaceB"]},
    "homelab": {"audience": "homelab", "scope": "homelab.read",
                "homelab_services": ["dns"], "homelab_hosts": ["host-a"]},
    "ha": {"audience": "ha", "scope": "ha.read",
           "ha_entities": ["sensor.qualified_example"], "ha_actions": ["state.read"]},
}


def service_variables(tmp_path, monkeypatch, audience):
    variables = policy_variables(tmp_path, monkeypatch)
    grant = copy.deepcopy(GRANTS[audience])
    preset = variables["chaldea_client_session_presets"][PRESET]
    preset["services"] = [grant]
    # project remains local authorization/accounting, independent of grant contents.
    variables["chaldea_client_session_ceilings"][0]["services"] = [copy.deepcopy(grant)]
    value = variables["chaldea_client_session_enrollments"][PRESET]
    value.pop("project")
    value.update(grant)
    value.update(issuer="https://auth.example.test/application/o/chaldea-" + audience + "/",
                 jwksUrl="https://auth.example.test/application/o/chaldea-" + audience + "/jwks/",
                 clientId="chaldea-" + audience + "-machine",
                 resource="https://" + audience + ".mcp.ryzhkov.dev/mcp")
    return variables


@pytest.fixture
def validator():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "session_enrollment", ROOT / "roles/chaldea_client/filter_plugins/session_enrollment.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(module, variables):
    return module.chaldea_session_enrollments(
        variables["chaldea_client_session_enrollments"],
        variables["chaldea_client_session_presets"],
        variables["chaldea_client_session_ceilings"], variables["fleet_home"])


@pytest.mark.parametrize("audience", GRANTS)
def test_new_profiles_render_exactly_idempotently_without_secret_opens(tmp_path, monkeypatch, audience):
    variables = service_variables(tmp_path, monkeypatch, audience)
    provision()
    provision_app_password()
    # Every Python process, including remote Ansible modules, refuses an attempt
    # to open an app-password. stat/lstat are allowed. No secret bytes are read.
    audit = tmp_path / "audit"
    audit.mkdir()
    marker = audit / "opened"
    (audit / "sitecustomize.py").write_text(
        "import os, sys\n"
        "def audit(event, args):\n"
        "    if event == 'open' and isinstance(args[0], (str, bytes)) "
        "and os.fsdecode(args[0]).endswith('.app-password'):\n"
        "        with open(" + repr(str(marker)) + ", 'w') as out: out.write('attempt')\n"
        "        raise PermissionError('fixture forbids secret open')\n"
        "sys.addaudithook(audit)\n")
    monkeypatch.setenv("PYTHONPATH", str(audit))
    extra = protected_tree(tmp_path)
    ok(run(tmp_path, variables, extra, check=True))
    path = Path(extra["chaldea_client_session_policy_path"])
    assert not path.exists()
    ok(run(tmp_path, variables, extra))
    rendered = path.read_bytes()
    assert json.loads(rendered)["enrollments"] == variables["chaldea_client_session_enrollments"]
    assert json.loads(rendered)["presets"][PRESET]["services"] == [GRANTS[audience]]
    assert b'"project": "projectA"' in rendered
    assert SECRET.encode() not in rendered
    repeated = run(tmp_path, variables, extra)
    ok(repeated)
    assert "changed=0" in repeated.stdout
    assert not marker.exists(), "the real role attempted to open an app-password"


# Mirrored closed-contract refusals. Mutate the enrollment and matching grant
# together where appropriate, so a schema failure cannot hide behind equality.
INVALID_GRANTS = [
    ("ov", {"scope": "ov.write"}),
    *[("ov", {"ov_namespaces": roots}) for roots in (
        None, [], ["viking://resources/a"] * 2,
        ["viking://resources/a", "viking://resources/a/b"],
        ["viking://resources/."], ["viking://resources/a/../b"],
        ["viking://resources/a//b"], ["viking://resources/a/"],
        ["viking://resources/%61"], ["viking://resources/*"],
        ["viking://resources/é"], ["viking://resources/" + "a" * 1006],
        ["viking://resources/n" + str(i) for i in range(17)], "viking://resources/a")],
    ("homelab", {"scope": "homelab.read homelab.write"}),
    *[("homelab", {field: values}) for field in ("homelab_services", "homelab_hosts")
      for values in (None, ["a"] * 2, ["*"], ["bad.name"], ["_bad"], ["a" * 65],
                     ["a" + str(i) for i in range(129)], "a")],
    *[("ha", {"scope": scope}) for scope in
      ("ha.write", "ha.read ha.read", " ha.read", "ha.read  ha.control", "ha.read\tha.control")],
    *[("ha", {"ha_entities": entities}) for entities in
      (None, [], ["sensor.a"] * 2, ["climate.a"], ["sensor.A"], ["sensor.*"],
       ["sensor.a.b"], ["sensor." + "a" * 97], ["sensor.a" + str(i) for i in range(65)])],
    *[("ha", {"ha_actions": actions}) for actions in
      (None, [], ["state.read"] * 2, ["*"], ["light.control"], ["switch.control"], ["service.call"])],
    ("ov", {"project": "projectA"}), ("ha", {"homelab_hosts": []}),
    ("homelab", {"grants": []}), ("ha", {"claims": {}}),
]


@pytest.mark.parametrize("audience,patch", INVALID_GRANTS)
def test_invalid_closed_grants(validator, tmp_path, monkeypatch, audience, patch):
    variables = service_variables(tmp_path, monkeypatch, audience)
    variables["chaldea_client_session_enrollments"][PRESET].update(patch)
    variables["chaldea_client_session_presets"][PRESET]["services"][0].update(patch)
    with pytest.raises(validator.AnsibleFilterError):
        validate(validator, variables)


@pytest.mark.parametrize("field,value", [
    ("audience", "jocasta"), ("audience", None), ("audience", ["ov"]),
    ("scope", None), ("issuer", "https://auth.example.test/application/o/p"),
    ("issuer", "https://auth.example.test/application/o/../p/"),
    ("issuer", "https://auth.example.test/application//p/"),
    ("issuer", "https://auth.example.test:0444/application/o/p/"),
    ("jwksUrl", "https://auth.example.test/other/jwks/"),
    ("tokenUrl", "https://auth.example.test/application/o/p/token/"),
    ("resource", "https://ov.mcp.ryzhkov.dev/mcp/"),
    ("resource", "https://ha.mcp.ryzhkov.dev/mcp"),
    ("resource", None), ("maxTokenSeconds", True),
    ("secretFile", "/etc/shadow"), ("project", "projectA"), ("claims", {}),
])
def test_new_enrollment_closed_fields_and_urls(validator, tmp_path, monkeypatch, field, value):
    variables = service_variables(tmp_path, monkeypatch, "ov")
    variables["chaldea_client_session_enrollments"][PRESET][field] = value
    with pytest.raises(validator.AnsibleFilterError):
        validate(validator, variables)


@pytest.mark.parametrize("audience", GRANTS)
def test_exact_payload_and_one_service(validator, tmp_path, monkeypatch, audience):
    variables = service_variables(tmp_path, monkeypatch, audience)
    original = copy.deepcopy(variables)
    assert validate(validator, variables) is True
    assert variables == original
    p = variables["chaldea_client_session_presets"][PRESET]
    p["services"].append(copy.deepcopy(SERVICES[0]))
    with pytest.raises(validator.AnsibleFilterError, match="one service"):
        validate(validator, variables)
    p["services"] = [copy.deepcopy(GRANTS[audience])]
    variables["chaldea_client_session_enrollments"] = {}
    with pytest.raises(validator.AnsibleFilterError, match="needs enrollment"):
        validate(validator, variables)


@pytest.mark.parametrize("audience,field,values", [
    ("ov", "ov_namespaces", ["viking://resources/namespaceB", "viking://resources/namespaceA/child"]),
    ("homelab", "homelab_services", []),
    ("ha", "ha_entities", ["sensor.other"]),
    ("ha", "scope", "ha.control"),
])
def test_changed_or_reordered_payload_refuses(validator, tmp_path, monkeypatch, audience, field, values):
    variables = service_variables(tmp_path, monkeypatch, audience)
    variables["chaldea_client_session_enrollments"][PRESET][field] = values
    with pytest.raises(validator.AnsibleFilterError):
        validate(validator, variables)


@pytest.mark.parametrize("audience", GRANTS)
def test_static_ceiling_containment_and_legacy_parse_only(validator, tmp_path, monkeypatch, audience):
    variables = service_variables(tmp_path, monkeypatch, audience)
    c = variables["chaldea_client_session_ceilings"][0]
    grant = c["services"][0]
    if audience == "ov":
        grant["ov_namespaces"] = ["viking://resources/namespaceA", "viking://resources/namespaceB"]
    elif audience == "homelab":
        grant["homelab_services"].append("other")
        grant["homelab_hosts"].append("host-b")
    else:
        grant["scope"] = "ha.control ha.read"
        grant["ha_entities"].append("light.a")
        grant["ha_actions"].append("light.control")
    c["services"].append({"audience": "unrelated", "grants": [{"resource": "legacy", "actions": ["get"]}]})
    assert validate(validator, variables)
    if audience == "ov":
        grant["ov_namespaces"] = ["viking://resources/namespace", "viking://resources/namespaceB"]
    elif audience == "homelab":
        grant["homelab_hosts"] = []
    else:
        grant["ha_actions"] = ["light.control"]
    with pytest.raises(validator.AnsibleFilterError, match="one admitting ceiling"):
        validate(validator, variables)


def test_no_merged_ceilings_or_legacy_grant_reinterpretation(validator, tmp_path, monkeypatch):
    variables = service_variables(tmp_path, monkeypatch, "ov")
    ceilings = variables["chaldea_client_session_ceilings"]
    ceilings.append(copy.deepcopy(ceilings[0]))
    ceilings[0]["services"][0]["ov_namespaces"] = ["viking://resources/namespaceA"]
    ceilings[1]["services"][0]["ov_namespaces"] = ["viking://resources/namespaceB"]
    with pytest.raises(validator.AnsibleFilterError, match="one admitting ceiling"):
        validate(validator, variables)
    ceilings[0]["services"] = [{"audience": "ov", "grants": [{"resource": "namespaceA", "actions": ["get"]}]}]
    with pytest.raises(validator.AnsibleFilterError):
        validate(validator, variables)


@pytest.mark.parametrize("failure", ["account", "secret", "provider", "client"])
def test_new_presets_isolate_accounts_secrets_and_service_providers(validator, tmp_path, monkeypatch, failure):
    variables = service_variables(tmp_path, monkeypatch, "ov")
    # Build the second service without re-running the disk fixture factory.
    key = "ha-reader"
    p = copy.deepcopy(variables["chaldea_client_session_presets"][PRESET])
    p["services"] = [copy.deepcopy(GRANTS["ha"])]
    variables["chaldea_client_session_presets"][key] = p
    variables["chaldea_client_session_ceilings"][0]["services"].append(copy.deepcopy(GRANTS["ha"]))
    first = variables["chaldea_client_session_enrollments"][PRESET]
    e = copy.deepcopy(first)
    for field in ("audience", "scope", "ov_namespaces"):
        e.pop(field)
    e.update(GRANTS["ha"])
    e.update(issuer="https://auth.example.test/application/o/ha/",
             jwksUrl="https://auth.example.test/application/o/ha/jwks/",
             clientId="ha-machine", username="ha-reader",
             resource="https://ha.mcp.ryzhkov.dev/mcp",
             secretFile=str(Path.home() / ".config/chaldea/authentik" / (key + ".app-password")))
    variables["chaldea_client_session_enrollments"][key] = e
    assert validate(validator, variables)
    if failure == "account":
        e["username"] = first["username"]
    elif failure == "secret":
        e["secretFile"] = first["secretFile"]
    elif failure == "provider":
        e["issuer"], e["jwksUrl"] = first["issuer"], first["jwksUrl"]
    else:
        e["clientId"] = first["clientId"]
    with pytest.raises(validator.AnsibleFilterError):
        validate(validator, variables)


def test_explicit_empty_homelab_and_ha_scope_forms(validator, tmp_path, monkeypatch):
    variables = service_variables(tmp_path, monkeypatch, "homelab")
    for obj in (variables["chaldea_client_session_presets"][PRESET]["services"][0],
                variables["chaldea_client_session_enrollments"][PRESET]):
        obj.update(homelab_services=[], homelab_hosts=[])
    assert validate(validator, variables)
    for scope in ("ha.read", "ha.control", "ha.read ha.control", "ha.control ha.read"):
        grant = copy.deepcopy(GRANTS["ha"])
        grant["scope"] = scope
        grant["ha_actions"] = ["state.read"] if scope == "ha.read" else ["light.control"]
        assert validator.service(grant) == grant


def test_policy_size_counts_utf8_bytes_at_exact_limit(validator):
    assert validator.chaldea_session_policy_size("a" * 65536)
    assert validator.chaldea_session_policy_size("é" * 32768)
    for text in ("a" * 65537, "é" * 32769):
        with pytest.raises(validator.AnsibleFilterError, match="64 KiB"):
            validator.chaldea_session_policy_size(text)


@pytest.mark.parametrize("failure", ["grant", "url", "missing", "size"])
def test_new_refusals_precede_secret_stat_and_all_writes(tmp_path, monkeypatch, failure):
    variables = service_variables(tmp_path, monkeypatch, "ov")
    e = variables["chaldea_client_session_enrollments"][PRESET]
    if failure == "grant":
        e["ov_namespaces"] = None
    elif failure == "url":
        e["jwksUrl"] = "https://auth.example.test/wrong/"
    elif failure == "missing":
        variables["chaldea_client_session_enrollments"] = {}
    else:
        variables["chaldea_client_session_presets"][PRESET]["prompt"] = "é" * 65536
    provision()
    extra = protected_tree(tmp_path)
    result = run(tmp_path, variables, extra)
    assert result.returncode != 0
    assert "Inspect operator-provisioned" not in result.stdout
    assert not (tmp_path / "protected/etc/chaldea").exists()
    assert not (Path.home() / ".config/chaldea/waits.json").exists()


@pytest.mark.parametrize("audience", GRANTS)
def test_missing_arrays_and_invalid_typed_ceilings_refuse(validator, tmp_path, monkeypatch, audience):
    variables = service_variables(tmp_path, monkeypatch, audience)
    fields = validator.FIELDS[audience]
    for field in fields:
        broken = copy.deepcopy(variables)
        del broken["chaldea_client_session_enrollments"][PRESET][field]
        del broken["chaldea_client_session_presets"][PRESET]["services"][0][field]
        with pytest.raises(validator.AnsibleFilterError):
            validate(validator, broken)
        broken = copy.deepcopy(variables)
        broken["chaldea_client_session_ceilings"][0]["services"][0][field] = None
        with pytest.raises(validator.AnsibleFilterError):
            validate(validator, broken)
    hybrid = copy.deepcopy(variables)
    hybrid["chaldea_client_session_ceilings"][0]["services"][0]["grants"] = []
    with pytest.raises(validator.AnsibleFilterError, match="legacy service fields"):
        validate(validator, hybrid)


@pytest.mark.parametrize("field,value", [
    ("project", "other"), ("maxSeconds", 1799), ("maxSeconds", True),
    ("destinations", []),
])
def test_ceiling_must_admit_the_whole_preset(validator, tmp_path, monkeypatch, field, value):
    variables = service_variables(tmp_path, monkeypatch, "ha")
    variables["chaldea_client_session_ceilings"][0][field] = value
    with pytest.raises(validator.AnsibleFilterError, match="one admitting ceiling"):
        validate(validator, variables)


def test_grant_boundaries_accept_without_normalization(validator):
    prefix = "viking://resources/"
    roots = [prefix + "x" * (1024 - len(prefix))] + [prefix + "n" + str(i) for i in range(15)]
    grants = [
        {"audience": "ov", "scope": "ov.read", "ov_namespaces": roots},
        {"audience": "homelab", "scope": "homelab.read",
         "homelab_services": ["s" + str(i) for i in range(128)],
         "homelab_hosts": ["h" + str(i) for i in range(128)]},
        {"audience": "ha", "scope": "ha.control ha.read",
         "ha_entities": ["binary_sensor." + "x" * 96] + ["sensor.n" + str(i) for i in range(63)],
         "ha_actions": ["switch.control", "state.read", "light.control"]},
    ]
    for grant in grants:
        before = copy.deepcopy(grant)
        assert validator.service(grant) == before
        assert grant == before


def test_legacy_enrollment_stays_unmodified(validator, tmp_path, monkeypatch):
    variables = policy_variables(tmp_path, monkeypatch)
    before = copy.deepcopy(variables)
    # Preserve unrelated parse-only ceiling entries.
    variables["chaldea_client_session_ceilings"][0]["services"] = copy.deepcopy(SERVICES) + [
        {"audience": "ov", "grants": [{"resource": "old", "actions": ["get"]}]}]
    assert validate(validator, variables)
    assert variables["chaldea_client_session_enrollments"] == before["chaldea_client_session_enrollments"]
    assert variables["chaldea_client_session_presets"] == before["chaldea_client_session_presets"]


def test_secret_path_cannot_follow_noncanonical_home(validator, tmp_path, monkeypatch):
    variables = policy_variables(tmp_path, monkeypatch)
    variables["fleet_home"] += "/../other"
    variables["chaldea_client_session_enrollments"][PRESET]["secretFile"] = (
        variables["fleet_home"] + "/.config/chaldea/authentik/" + PRESET + ".app-password")
    with pytest.raises(validator.AnsibleFilterError, match="secretFile"):
        validate(validator, variables)
