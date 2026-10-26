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
    assert "jocasta" in laptop["chaldea_laptop_jocasta_profiles"]["jocasta-tooling-codex"]["disabled_servers"]
    assert laptop["chaldea_laptop_jocasta_profiles"]["jocasta-tooling-claude"]["server"] == "jocasta_tooling"


def test_actual_ansible_selection_honors_managed_absence_and_keeps_oauth(tmp_path):
    import subprocess
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"].startswith("Select explicit"))
    unrelated = {"name": "unrelated", "url": "https://other.example/mcp", "providers": ["codex"]}
    managed = {"name": "jocasta", "url": URL, "providers": ["claude", "codex"],
               "auth_mode": "managed_helper", "helper_host": "laptop"}
    cases = [
        (True, [unrelated, {"name": "jocasta", "state": "absent"}],
         [unrelated, {**managed, "state": "absent"}]),
        (True, [], [{**managed, "state": "present"}]),
        (False, [unrelated, {"name": "jocasta", "state": "absent"}],
         [unrelated, {"name": "jocasta", "state": "absent"}]),
    ]
    play_tasks = []
    for index, (enabled, remotes, expected) in enumerate(cases):
        play_tasks.extend([
            {"name": "Select case " + str(index),
             "ansible.builtin.set_fact": select["ansible.builtin.set_fact"],
             "vars": {"webmcp_interactive_enabled": enabled,
                      "mcp_registrations_remote_servers": remotes}},
            {"name": "Verify case " + str(index),
             "ansible.builtin.assert": {"that": ["mcp_registrations_effective_remote_servers == expected"]},
             "vars": {"expected": expected}},
        ])
    play = tmp_path / "selection.yml"
    play.write_text(yaml.safe_dump([{"hosts": "laptop", "connection": "local",
                                   "gather_facts": False, "tasks": play_tasks}]))
    result = subprocess.run(["ansible-playbook", "-i", "laptop,", str(play)],
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("distinct_homes", [False, True])
def test_inventory_selects_four_managed_hosts_with_local_sources(tmp_path, distinct_homes):
    import subprocess
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"].startswith("Select explicit"))
    select_ov = next(t for t in tasks if t["name"].startswith("Select the closed laptop OV"))
    homes = {host: str(tmp_path / host) if distinct_homes else "/home/igor" for host in HOSTS}
    architectures = {host: "aarch64" if host == "laptop" else "x86_64" for host in HOSTS}
    # Shared architecture pins, except the held laptop's own pin for the
    # reviewed aarch64 helper with the OV mode (build 031e3362).
    pins = {
        "aarch64": "f936deea9705fa4237f5c74760ccd51e1ab473fffa498836002f68b8c05036ba",
        "x86_64": "667cd06e83a091d607306e6486ff079d0065038abf2db64b87234d15492bd6ed",
    }
    host_pins = {host: pins[architectures[host]] for host in HOSTS}
    host_pins["laptop"] = "ff9ccff552680ce1e86b3bed4c68c1a7902a0a0e7a0b5f9de174bc3d74b568fc"
    ov_entry = {"name": "ov", "url": "https://ov.mcp.ryzhkov.dev/mcp", "providers": ["codex"],
                "auth_mode": "managed_helper", "helper_host": "laptop", "state": "present"}
    play = tmp_path / "inventory-selection.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "agent_hosts", "gather_facts": False,
        "vars": {"homes": homes, "architectures": architectures, "host_pins": host_pins, "ov_entry": ov_entry,
                 "ansible_facts": {
                     "user_dir": "{{ homes[inventory_hostname] }}",
                     "architecture": "{{ architectures[inventory_hostname] }}"}},
        "tasks": [
            {**select, "vars": {"mcp_registrations_remote_servers":
                "{{ hostvars[inventory_hostname].mcp_registrations_remote_servers | default([]) }}"}},
            {**select_ov, "vars": {"mcp_registrations_remote_servers":
                "{{ hostvars[inventory_hostname].mcp_registrations_remote_servers | default([]) }}"}},
            {"ansible.builtin.assert": {"that": [
                "mcp_registrations_effective_remote_servers == expected + "
                "([ov_entry] if inventory_hostname == 'laptop' else [])",
                "(webmcp_interactive_ov_enabled | default(false) | bool) == (inventory_hostname == 'laptop')",
                "webmcp_interactive_helper_sha256 == host_pins[inventory_hostname]",
                "webmcp_interactive_helper_checksums == pins",
                "webmcp_interactive_enabled | bool",
                "inventory_hostname == 'laptop' or webmcp_interactive_laptop_qualified | bool",
                "webmcp_interactive_helper_source == '/usr/local/libexec/webmcp-interactive-headers'",
                "webmcp_interactive_credential_source == homes[inventory_hostname] ~ "
                "'/.config/webmcp-interactive/enrollment.json'",
                "agent_config_fleet_tools_profile.mcp == ['ov-memory', 'jocasta']"]},
             "vars": {"pins": pins, "expected": [
                 {"name": "jocasta", "url": URL, "providers": ["claude", "codex"],
                  "auth_mode": "managed_helper", "helper_host": "{{ inventory_hostname }}",
                  "state": "present"}]}},
        ]}]))
    result = subprocess.run(["ansible-playbook", "-i", str(ROOT / "inventory/hosts.yml"), str(play)],
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for host in HOSTS:
        assert host in result.stdout


@pytest.mark.parametrize("failure", ["unsupported_architecture", "missing_helper"])
def test_inventory_refuses_unready_hosts_before_delivery(tmp_path, failure):
    import subprocess
    tasks = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    # Execute the unchanged role preflight against actual inventory. All paths
    # are synthetic; no privileged installation or native registration can run.
    play = tmp_path / "unready.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "agent_hosts", "gather_facts": False,
        "vars": {
            "ansible_facts": {"user_dir": str(tmp_path),
                              "architecture": "unsupported" if failure == "unsupported_architecture" else "x86_64"},
            "webmcp_interactive_helper_source": str(tmp_path / "missing-helper")},
        "tasks": tasks[:3]}]))
    result = subprocess.run(["ansible-playbook", "-i", str(ROOT / "inventory/hosts.yml"), str(play)],
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True)
    assert result.returncode != 0
    expected_task = ("Require selected host and laptop qualification before staging"
                     if failure == "unsupported_architecture" else "Require exact reviewed helper bytes")
    assert expected_task in result.stdout
    assert "Inspect existing helper ownership" not in result.stdout
    assert "Stage only a protected per-host enrollment" not in result.stdout
    assert not (tmp_path / ".config").exists()
    for host in HOSTS:
        assert host in result.stdout


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
    with pytest.raises(FileNotFoundError):
        mod.protected_read(str(path), "laptop")
    assert not path.exists()
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
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError):
        mod.protected_read(str(path), "laptop")
    tmp_path.chmod(0o700)
    link = tmp_path / "link"
    os.link(path, link)
    with pytest.raises(ValueError):
        mod.protected_read(str(path), "laptop")
    link.unlink()
    path.unlink()
    path.symlink_to("missing")
    with pytest.raises(OSError):
        mod.protected_read(str(path), "laptop")


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("reuse_installed", [False, True])
def test_ansible_keeps_protected_json_as_exact_text(tmp_path, reuse_installed, host):
    import re
    import subprocess
    home = tmp_path / "home"
    private = home / ".config/webmcp-interactive"
    private.mkdir(parents=True, mode=0o700)
    target = private / "enrollment.json"
    source = target if reuse_installed else private / (host + ".json")
    value = {"version": 1, "owner": "00000000-0000-4000-8000-000000000000", "host": host,
             "username": "webmcp-interactive-" + host, "password": "synthetic-private-password", "generation": 1}
    content = json.dumps(value, sort_keys=True, separators=(",", ":"))
    source.write_text(content)
    source.chmod(0o600)
    tasks = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    delivery = next(t for t in tasks if t["name"] == "Stage only a protected per-host enrollment")
    install = next(t for t in tasks if t["name"] == "Install exact public native helper")
    helper = tmp_path / "installed-helper"
    helper_source = helper if reuse_installed else tmp_path / "staged-helper"
    helper_source.write_text("synthetic public helper fixture\n")
    helper_source.chmod(0o755)
    # Keep the actual copy task, with its fixed privileged destination moved to scratch.
    install = {**install, "become": False, "ansible.builtin.copy": {
        **install["ansible.builtin.copy"], "dest": str(helper),
        "owner": str(os.getuid()), "group": str(os.getgid())}}
    play = tmp_path / "delivery.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Check actual protected delivery and local pull reuse", "hosts": host,
        "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(home), "ansible_facts": {"user_uid": os.getuid()},
                 "webmcp_interactive_credential_source": str(source),
                 "webmcp_interactive_previous_credential_sha256": "",
                 "webmcp_interactive_helper_source": str(helper_source)},
        "tasks": [delivery, install]}]))
    env = {**os.environ, "ANSIBLE_LOOKUP_PLUGINS": str(ROOT / "roles/webmcp_interactive/lookup_plugins"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    for repeat in range(2):
        result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert target.read_text() == content
        assert helper.read_text() == "synthetic public helper fixture\n"
        assert helper.stat().st_mode & 0o777 == 0o755
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.stat().st_uid == os.getuid()
        assert private.stat().st_mode & 0o777 == 0o700
        assert "synthetic-private-password" not in result.stdout + result.stderr
        if reuse_installed or repeat:
            assert re.search(re.escape(host) + r"\s+: ok=\d+\s+changed=0\s", result.stdout)
