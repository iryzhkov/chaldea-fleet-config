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
