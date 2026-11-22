"""Closed HoloNet library management native registrations. No helper/auth/backend calls."""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet import reader
from test_webmcp_managed_holonet_seed_join import seed_join
from test_webmcp_managed_holonet_writer import writer
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
URL = "https://media.mcp.ryzhkov.dev/mcp"
FLAG = "webmcp_interactive_holonet_library_enabled"
HOSTS = ("laptop", "omarchy-pc")
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
SECRET_BYTES = "FixtureLibraryWriterPass0123456"


def library(host="laptop", **changes):
    return {"name": "holonet_library", "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": host} | changes


@pytest.mark.parametrize("host", HOSTS)
def test_codex_repeat_inverse_preserves_old_profiles(tmp_path, host):
    path = tmp_path / "config.toml"
    for profile in (reader(), writer(), seed_join()):
        call("codex", codex_config=str(path), **profile)
    before = tomllib.loads(path.read_text())
    assert call("codex", codex_config=str(path), **library(host))["changed"]
    result = tomllib.loads(path.read_text())
    assert result["mcp_servers"]["holonet_library"]["http_headers_helper"] == (
        "/usr/local/libexec/webmcp-interactive-headers holonet-library " + host)
    assert not call("codex", codex_config=str(path), **library(host))["changed"]
    assert call("codex", codex_config=str(path), **library(host, state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


@pytest.mark.parametrize("host", HOSTS)
def test_claude_repeat_inverse_preserves_neighbors(tmp_path, host):
    path = tmp_path / "claude.json"
    before = {"mcpServers": {"other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    args = {"claude_config": str(path),
            "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", **args, **library(host))["changed"]
    doc = json.loads(path.read_text())
    assert doc["mcpServers"]["holonet_library"] == {
        "type": "http",
        "url": URL,
        "headersHelper": "/usr/local/libexec/webmcp-interactive-headers holonet-library " + host,
    }
    assert not call("claude", **args, **library(host))["changed"]
    assert call("claude", **args, **library(host, state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("provider,change", [
    ("opencode", {}),
    ("opencode", {"helper_host": "omarchy-pc"}),
    ("antigravity", {}),
    ("antigravity", {"helper_host": "omarchy-pc"}),
    ("codex", {"helper_host": "agent-a"}),
    ("claude", {"helper_host": "agent-b"}),
    ("codex", {"helper_host": "gaming-pc"}),
    ("codex", {"url": URL + "/"}),
    ("codex", {"extra": {"http_headers_helper": "arbitrary"}}),
    ("claude", {"extra": {"headers": {"Authorization": "synthetic"}}}),
])
def test_closed_registration(provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider,
                                      {"extra": {}, **library(**change)})


def _run_play(tmp_path, host, tasks, extra_vars=None):
    play = tmp_path / f"play-{host}.yml"
    doc = {"hosts": host, "connection": "local", "gather_facts": False, "tasks": tasks}
    if extra_vars:
        doc["vars"] = extra_vars
    play.write_text(yaml.safe_dump([doc]))
    return subprocess.run(["ansible-playbook", "-i", host + ",", str(play)],
                          env=ENV, capture_output=True, text=True)


def test_default_off_and_real_selection(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    # Only the two approved host identities opt in, after issuer enrollment and
    # consumer deployment (2026-11-22).
    approved = {ROOT / "inventory/host_vars/laptop/holonet-interactive.yml",
                ROOT / "inventory/host_vars/omarchy-pc/ov-memory.yml"}
    selected = set()
    for path in (ROOT / "inventory").rglob("*.yml"):
        data = yaml.safe_load(path.read_text())
        if isinstance(data, dict) and FLAG in data:
            assert path in approved and data[FLAG] is True, f"{path} selects {FLAG}"
            selected.add(path)
    assert selected == approved

    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"] ==
                  "Select the closed HoloNet library manager on explicit opt-in")
    base, _ = selection_tasks()
    for host in HOSTS:
        checks = []
        for parent, enabled in ((True, False), (True, True), (False, True)):
            values = {"webmcp_interactive_enabled": parent, FLAG: enabled,
                      "mcp_registrations_remote_servers": [reader(), writer(), seed_join()]}
            checks += [
                {**base, "vars": values},
                {**select, "vars": values},
                {"ansible.builtin.assert": {"that": [
                    "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'holonet_library') | list | length == expected",
                ]}, "vars": {"expected": 1 if parent and enabled else 0}},
            ]
        result = _run_play(tmp_path, host, checks)
        assert result.returncode == 0, result.stdout + result.stderr


def test_role_guard_requires_strict_bool_and_bound_host_uid(tmp_path):
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    guard = {"ansible.builtin.assert": {"that": [
        e for e in role[0]["ansible.builtin.assert"]["that"] if FLAG in e]}}
    assert len(guard["ansible.builtin.assert"]["that"]) == 2
    for enabled, host, uid, host_id, refused in (
            (False, "laptop", 1001, False, False),
            (True, "laptop", 1001, True, False),
            (True, "omarchy-pc", 1000, True, False),
            (True, "laptop", 1001, False, True),
            (True, "omarchy-pc", 1000, False, True),
            ("true", "laptop", 1001, True, True),
            ("true", "omarchy-pc", 1000, True, True),
            (True, "laptop", 1000, True, True),
            (True, "omarchy-pc", 1001, True, True),
            (True, "agent-a", 1000, True, True),
            (True, "agent-b", 1000, True, True),
    ):
        checks = [
            {**guard, "vars": {FLAG: enabled, "chaldea_host_identity_enabled": host_id,
                               "ansible_facts": {"user_uid": uid}},
             "ignore_errors": True, "register": "guard_result"},
            {"ansible.builtin.assert": {"that": ["guard_result.failed | default(false) == refused"]},
             "vars": {"refused": refused}},
        ]
        result = _run_play(tmp_path, host, checks)
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("unsafe", [None, "missing", "writer-only", "group-readable", "shared-directory", "symlink", "oversized", "short"])
def test_library_credential_custody_uses_host_identity_without_fallback(tmp_path, unsafe):
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    # No separate holonet-recommendations.app-password precheck for holonet_library;
    # custody is enforced through host-identity.yml on host.app-password.
    assert not [t for t in role if "holonet-recommendations" in str(t)]
    check = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/host-identity.yml").read_text())[:2]
    assert check[0]["ansible.builtin.stat"]["get_checksum"] is False
    assert check[0]["ansible.builtin.stat"]["follow"] is False

    home = tmp_path / "home"
    private = home / ".config/chaldea/authentik"
    private.mkdir(parents=True)
    for parent in (home, home / ".config", home / ".config/chaldea"):
        parent.chmod(0o755)
    private.chmod(0o700)
    target = private / "host.app-password"
    target.write_text(SECRET_BYTES)
    target.chmod(0o600)

    if unsafe == "missing":
        target.unlink()
    elif unsafe == "writer-only":
        # holonet-recommendations.app-password must never satisfy holonet_library.
        target.rename(private / "holonet-recommendations.app-password")
    elif unsafe == "group-readable":
        target.chmod(0o640)
    elif unsafe == "shared-directory":
        private.chmod(0o750)
    elif unsafe == "symlink":
        real = tmp_path / "elsewhere"
        real.write_text(SECRET_BYTES)
        real.chmod(0o600)
        target.unlink()
        target.symlink_to(real)
    elif unsafe == "oversized":
        target.write_text("x" * 257)
    elif unsafe == "short":
        target.write_text("x" * 15)

    result = _run_play(tmp_path, "omarchy-pc", check, extra_vars={
        "fleet_home": str(home),
        FLAG: True,
        "chaldea_host_identity_enabled": True,
        "ansible_facts": {"user_uid": os.getuid()},
    })
    assert SECRET_BYTES not in result.stdout + result.stderr
    if unsafe is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "host.app-password is missing or unsafe" in result.stdout
