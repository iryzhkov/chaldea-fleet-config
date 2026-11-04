"""Fixed same-account janitor registration, isolated from writer and reader."""
import json
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet_writer import writer
from test_webmcp_managed_holonet import reader, _ansible
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
FLAG = "webmcp_interactive_holonet_janitor_enabled"
URL = "https://media.mcp.ryzhkov.dev/mcp"
HELPER = "/usr/local/libexec/webmcp-interactive-headers holonet-janitor laptop"


def janitor(**changes):
    return {"name": "holonet_janitor", "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": "laptop"} | changes


def test_janitor_codex_repeat_and_inverse_preserve_writer_reader(tmp_path):
    path = tmp_path / "config.toml"
    call("codex", codex_config=str(path), **reader())
    call("codex", codex_config=str(path), **writer())
    before = tomllib.loads(path.read_text())
    assert call("codex", codex_config=str(path), **janitor())["changed"]
    assert tomllib.loads(path.read_text())["mcp_servers"]["holonet_janitor"]["http_headers_helper"] == HELPER
    assert not call("codex", codex_config=str(path), **janitor())["changed"]
    assert call("codex", codex_config=str(path), **janitor(state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


def test_janitor_claude_preserves_neighbors(tmp_path):
    path = tmp_path / "claude.json"
    before = {"mcpServers": {"other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    args = {"claude_config": str(path),
            "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", **args, **janitor())["changed"]
    assert not call("claude", **args, **janitor())["changed"]
    assert call("claude", **args, **janitor(state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("provider,change", [
    ("opencode", {}), ("codex", {"helper_host": "agent-a"}),
    ("claude", {"helper_host": "omarchy-pc"}), ("codex", {"url": URL + "/"}),
    ("codex", {"extra": {"headers": {"Authorization": "synthetic"}}}),
    ("claude", {"helper_profile": "ov-full"}),
])
def test_janitor_closed_registration(provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider, {"extra": {}, **janitor(**change)})


def test_janitor_default_off_and_real_selection(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    activation = ROOT / "inventory/host_vars/laptop/holonet-interactive.yml"
    assert yaml.safe_load(activation.read_text())[FLAG] is True
    assert all(FLAG not in p.read_text() for p in (ROOT / "inventory").rglob("*.yml") if p != activation)
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"] == "Select the closed laptop HoloNet janitor on explicit opt-in")
    base, _ = selection_tasks()
    checks = []
    for index, enabled in enumerate([False, True]):
        values = {"webmcp_interactive_enabled": True, FLAG: enabled, "mcp_registrations_remote_servers": []}
        checks += [{**base, "vars": values}, {**select, "vars": values},
                   {"ansible.builtin.assert": {"that": [
                       "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'holonet_janitor') | list | length == expected"]},
                    "vars": {"expected": 1 if enabled else 0}}]
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    # Execute the real janitor-only pre-write assertions without unrelated setup.
    guard = {"ansible.builtin.assert": {"that": [
        expression for expression in role[0]["ansible.builtin.assert"]["that"]
        if FLAG in expression]}}
    assert len(guard["ansible.builtin.assert"]["that"]) == 2
    for flag, host, uid, writer_enabled, refused in [
        (False, "laptop", 1001, False, False),
        (True, "laptop", 1001, True, False),
        ("true", "laptop", 1001, True, True),
        (True, "laptop", 0, True, True),
        (True, "laptop", 1001, False, True),
    ]:
        checks += [{**guard, "vars": {FLAG: flag, "ansible_facts": {"user_uid": uid},
                    "webmcp_interactive_holonet_writer_enabled": writer_enabled},
                    "ignore_errors": True, "register": "guard_result"},
                   {"ansible.builtin.assert": {"that": ["guard_result.failed | default(false) == refused"]},
                    "vars": {"refused": refused}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr
