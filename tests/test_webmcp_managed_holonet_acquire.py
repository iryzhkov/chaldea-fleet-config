"""Closed acquisition native registrations. No helper/auth/backend calls."""
import json
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet_seed_join import seed_join
from test_webmcp_managed_holonet_writer import writer
from test_webmcp_managed_holonet import reader, _ansible
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
URL = "https://media.mcp.ryzhkov.dev/mcp"
PURPOSES = ("read", "start", "media")


def acquire(purpose, **changes):
    return {"name": "holonet_acquire_" + purpose, "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": "laptop"} | changes


@pytest.mark.parametrize("purpose", PURPOSES)
def test_codex_repeat_inverse_preserves_old_profiles(tmp_path, purpose):
    path = tmp_path / "config.toml"
    for profile in (reader(), writer(), seed_join()):
        call("codex", codex_config=str(path), **profile)
    before = tomllib.loads(path.read_text())
    assert call("codex", codex_config=str(path), **acquire(purpose))["changed"]
    result = tomllib.loads(path.read_text())
    assert result["mcp_servers"]["holonet_acquire_" + purpose]["http_headers_helper"] == (
        "/usr/local/libexec/webmcp-interactive-headers holonet-acquire-" + purpose + " laptop")
    assert not call("codex", codex_config=str(path), **acquire(purpose))["changed"]
    assert call("codex", codex_config=str(path), **acquire(purpose, state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


@pytest.mark.parametrize("purpose", PURPOSES)
def test_claude_repeat_inverse_preserves_neighbors(tmp_path, purpose):
    path = tmp_path / "claude.json"
    before = {"mcpServers": {"other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    args = {"claude_config": str(path),
            "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", **args, **acquire(purpose))["changed"]
    assert not call("claude", **args, **acquire(purpose))["changed"]
    assert call("claude", **args, **acquire(purpose, state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("purpose", PURPOSES)
@pytest.mark.parametrize("provider,change", [
    ("opencode", {}), ("codex", {"helper_host": "agent-a"}),
    ("claude", {"helper_host": "omarchy-pc"}), ("codex", {"url": URL + "/"}),
    ("codex", {"extra": {"http_headers_helper": "arbitrary"}}),
    ("claude", {"extra": {"headers": {"Authorization": "synthetic"}}}),
])
def test_closed_registration(purpose, provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider,
                                      {"extra": {}, **acquire(purpose, **change)})


@pytest.mark.parametrize("purpose", PURPOSES)
def test_default_off_and_real_selection(tmp_path, purpose):
    flag = "webmcp_interactive_holonet_acquire_" + purpose + "_enabled"
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[flag] is False
    assert all(flag not in p.read_text() for p in (ROOT / "inventory").rglob("*.yml"))
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"] ==
        "Select the closed laptop HoloNet acquisition " + purpose + " on explicit opt-in")
    base, _ = selection_tasks()
    checks = []
    for parent, enabled in ((True, False), (True, True), (False, True)):
        values = {"webmcp_interactive_enabled": parent, flag: enabled,
                  "mcp_registrations_remote_servers": [reader(), writer(), seed_join()]}
        checks += [{**base, "vars": values}, {**select, "vars": values},
            {"ansible.builtin.assert": {"that": [
                "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'holonet_acquire_" +
                purpose + "') | list | length == expected"]},
             "vars": {"expected": 1 if parent and enabled else 0}}]
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    guard = {"ansible.builtin.assert": {"that": [
        e for e in role[0]["ansible.builtin.assert"]["that"] if flag in e]}}
    assert len(guard["ansible.builtin.assert"]["that"]) == 2
    for enabled, host, uid, writer_enabled, refused in (
            (False, "laptop", 1001, False, False), (True, "laptop", 1001, True, False),
            ("true", "laptop", 1001, True, True), (True, "laptop", 0, True, True),
            (True, "laptop", 1001, False, True), (True, "agent-a", 1001, True, True)):
        checks += [{**guard, "vars": {"inventory_hostname": host, flag: enabled,
                    "ansible_facts": {"user_uid": uid},
                    "webmcp_interactive_holonet_writer_enabled": writer_enabled},
                    "ignore_errors": True, "register": "guard_result"},
                   {"ansible.builtin.assert": {"that": [
                       "guard_result.failed | default(false) == refused"]},
                    "vars": {"refused": refused}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr
