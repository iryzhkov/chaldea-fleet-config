"""Managed helper mode is closed; public OAuth and unrelated native state survive.

Synthetic client configs only. These tests do not qualify official T3.
"""
import importlib.util
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, call, module_code
from test_mcp_remote_registration import CODEX_CONFIG, SECRET, SECRET_KEYS, URL, remote

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ["laptop", "agent-a", "agent-b", "omarchy-pc"]


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("provider,field", [("codex", "http_headers_helper"), ("claude", "headersHelper")])
def test_fixed_helper_registration_roundtrip_and_preservation(tmp_path, host, provider, field):
    path = tmp_path / ("config.toml" if provider == "codex" else "claude.json")
    other = {"type": "http", "url": "https://other.example/mcp", "headers": {"Authorization": SECRET}}
    if provider == "codex":
        path.write_text(CODEX_CONFIG)
        kwargs = {"codex_config": str(path)}
    else:
        path.write_text(json.dumps({"private": SECRET, "mcpServers": {"other": other}}))
        kwargs = {"claude_config": str(path), "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    params = dict(name="jocasta", transport="remote", url=URL, auth_mode="managed_helper", helper_host=host, **kwargs)
    result = call(provider, **params)
    assert result["changed"] and SECRET not in json.dumps(result)
    doc = tomllib.loads(path.read_text()) if provider == "codex" else json.loads(path.read_text())
    servers = doc["mcp_servers" if provider == "codex" else "mcpServers"]
    assert servers["jocasta"] == {"url": URL, field: module_code.HELPER + host, **({"type": "http"} if provider == "claude" else {})}
    if provider == "claude":
        assert doc["private"] == SECRET and servers["other"] == other
    else:
        assert servers["other"]["http_headers"]["Authorization"] == SECRET
    assert not call(provider, **params)["changed"]
    assert call(provider, state="absent", **params)["changed"]
    final = tomllib.loads(path.read_text()) if provider == "codex" else json.loads(path.read_text())
    assert "other" in final["mcp_servers" if provider == "codex" else "mcpServers"]


@pytest.mark.parametrize("change", [
    {"url": "https://other.example/mcp"}, {"helper_host": "homelab"}, {"name": "other"},
    {"extra": {"headers": {"Authorization": SECRET}}},
    {"extra": {"http_headers_helper": SECRET}}, {"extra": {"oauth": {"client_id": "other"}}},
])
def test_managed_mode_refuses_drift_before_native_write(tmp_path, change):
    path = tmp_path / "config.toml"
    params = dict(name="jocasta", transport="remote", url=URL, auth_mode="managed_helper",
                  helper_host="laptop", codex_config=str(path))
    with pytest.raises(Failed):
        call("codex", **(params | change))
    assert not path.exists()


def test_opencode_and_oauth_cannot_select_helper(tmp_path):
    with pytest.raises(Failed):
        call("codex", name="jocasta", command="/fixture", auth_mode="managed_helper")
    with pytest.raises(Failed):
        call("opencode", name="jocasta", transport="remote", url=URL, auth_mode="managed_helper",
             helper_host="laptop", opencode_config=str(tmp_path / "opencode.json"))
    for key in SECRET_KEYS:
        path = tmp_path / "config.toml"
        with pytest.raises(Failed):
            call("codex", codex_config=str(path), **remote("codex", extra={key: SECRET}))
        assert not path.exists()
    projected = module_code.public_projection("codex", {"http_headers_helper": SECRET})
    assert SECRET not in module_code.diff("jocasta", projected, {}, module_code.remote_view)["before"]


def test_activation_is_opt_in_and_profiles_unchanged():
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults["webmcp_interactive_enabled"] is False
    assert defaults["webmcp_interactive_laptop_qualified"] is False
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    stage = next(t for t in tasks if t["name"].startswith("Stage explicitly"))
    assert stage["when"] == "webmcp_interactive_enabled | default(false) | bool"
    assert stage["ansible.builtin.include_role"]["apply"]["tags"] == ["mcp_registrations"]
    strict = (ROOT / "roles/chaldea_client/templates/claude-profile-exec.py.j2").read_text()
    assert 'for name in ("--restricted", "--strict-mcp-config"):' in strict
    select = next(t for t in tasks if t["name"].startswith("Select explicit"))
    assert "else mcp_registrations_remote_servers" in select["ansible.builtin.set_fact"]["mcp_registrations_effective_remote_servers"]
    laptop = yaml.safe_load((ROOT / "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml").read_text())
    assert "jocasta" in laptop["chaldea_client_session_profiles"]["jocasta-tooling-codex"]["disabled_servers"]
    assert laptop["chaldea_client_session_profiles"]["jocasta-tooling-claude"]["server"] == "jocasta_tooling"


def test_remote_cli_failures_do_not_quote_output():
    from test_mcp_registration import FakeModule
    module = FakeModule()
    module.run_command = lambda argv: (1, SECRET, SECRET)
    with pytest.raises(Failed) as failure:
        module_code.run_remote(module, ["claude", "mcp", "add-json"])
    assert SECRET not in str(failure.value)


def load_private():
    spec = importlib.util.spec_from_file_location("webmcp_private", ROOT / "roles/webmcp_interactive/lookup_plugins/webmcp_private.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_protected_input_read_and_unsafe_metadata(tmp_path):
    mod = load_private()
    os.chmod(tmp_path, 0o700)
    path = tmp_path / "enrollment.json"
    value = {"version": 1, "owner": "00000000-0000-4000-8000-000000000000", "host": "laptop",
             "username": "webmcp-interactive-laptop", "password": "synthetic-private-password", "generation": 1}
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    assert json.loads(mod.protected_read(str(path), "laptop")) == value
    with pytest.raises(ValueError):
        mod.protected_read(str(path), "agent-a")
    path.chmod(0o640)
    with pytest.raises(ValueError):
        mod.protected_read(str(path), "laptop")
    path.chmod(0o600)
    link = tmp_path / "link"
    os.link(path, link)
    with pytest.raises(ValueError):
        mod.protected_read(str(path), "laptop")
    link.unlink()
    path.unlink()
    path.symlink_to("missing")
    with pytest.raises(OSError):
        mod.protected_read(str(path), "laptop")


def test_ansible_keeps_protected_json_as_exact_text(tmp_path):
    import hashlib
    import subprocess
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    source = private / "laptop.json"
    value = {"version": 1, "owner": "00000000-0000-4000-8000-000000000000", "host": "laptop",
             "username": "webmcp-interactive-laptop", "password": "synthetic-private-password", "generation": 1}
    content = json.dumps(value, sort_keys=True, separators=(",", ":"))
    source.write_text(content)
    source.chmod(0o600)
    target = private / "delivered.json"
    play = tmp_path / "delivery.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Check actual protected lookup and copy types", "hosts": "localhost",
        "connection": "local", "gather_facts": False,
        "tasks": [
            {"name": "Read private fixture", "ansible.builtin.set_fact": {
                "staged": "{{ lookup('webmcp_private', source, 'laptop') }}"}, "no_log": True},
            {"name": "Require exact text", "ansible.builtin.assert": {"that": [
                "staged is string", "staged | hash('sha256') == expected"]}, "no_log": True},
            {"name": "Deliver private fixture", "ansible.builtin.copy": {
                "content": "{{ staged }}", "dest": str(target), "mode": "0600", "follow": False},
             "no_log": True, "diff": False},
        ]}]))
    env = {**os.environ, "ANSIBLE_LOOKUP_PLUGINS": str(ROOT / "roles/webmcp_interactive/lookup_plugins"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play), "--extra-vars",
                             json.dumps({"source": str(source), "expected": hashlib.sha256(content.encode()).hexdigest()})],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text() == content
    assert "synthetic-private-password" not in result.stdout + result.stderr
