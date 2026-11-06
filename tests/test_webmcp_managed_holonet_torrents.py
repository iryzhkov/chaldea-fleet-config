"""Fixed same-account torrents registration, isolated from writer and reader."""
import json
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet_writer import writer
from test_webmcp_managed_holonet_janitor import janitor
from test_webmcp_managed_holonet import reader, _ansible
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
FLAG = "webmcp_interactive_holonet_torrents_enabled"
URL = "https://media.mcp.ryzhkov.dev/mcp"
HELPER = "/usr/local/libexec/webmcp-interactive-headers holonet-torrents laptop"


def torrents(**changes):
    return {"name": "holonet_janitor_torrents", "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": "laptop"} | changes


def test_torrents_codex_repeat_and_inverse_preserve_writer_reader(tmp_path):
    path = tmp_path / "config.toml"
    call("codex", codex_config=str(path), **reader())
    call("codex", codex_config=str(path), **writer())
    call("codex", codex_config=str(path), **janitor())
    before = tomllib.loads(path.read_text())
    assert call("codex", codex_config=str(path), **torrents())["changed"]
    assert tomllib.loads(path.read_text())["mcp_servers"]["holonet_janitor_torrents"]["http_headers_helper"] == HELPER
    assert not call("codex", codex_config=str(path), **torrents())["changed"]
    assert call("codex", codex_config=str(path), **torrents(state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


def test_torrents_claude_preserves_neighbors(tmp_path):
    path = tmp_path / "claude.json"
    before = {"mcpServers": {"other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    args = {"claude_config": str(path),
            "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", **args, **torrents())["changed"]
    assert not call("claude", **args, **torrents())["changed"]
    assert call("claude", **args, **torrents(state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("provider,change", [
    ("opencode", {}), ("codex", {"helper_host": "agent-a"}),
    ("claude", {"helper_host": "omarchy-pc"}), ("codex", {"url": URL + "/"}),
    ("codex", {"extra": {"headers": {"Authorization": "synthetic"}}}),
    ("claude", {"helper_profile": "ov-full"}),
    ("codex", {"extra": {"http_headers_helper": HELPER + " extra"}}),
    ("claude", {"extra": {"headersHelper": HELPER.replace("holonet-torrents", "holonet-janitor")}}),
])
def test_torrents_closed_registration(provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider, {"extra": {}, **torrents(**change)})


def test_torrents_default_off_and_real_selection(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    assert all(FLAG not in p.read_text() for p in (ROOT / "inventory").rglob("*.yml"))
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"] == "Select the closed laptop HoloNet torrents on explicit opt-in")
    base, _ = selection_tasks()
    checks = []
    for parent, enabled in [(True, False), (True, True), (False, True)]:
        values = {"webmcp_interactive_enabled": parent, FLAG: enabled,
                  "mcp_registrations_remote_servers": [reader(), writer(), janitor()]}
        checks += [{**base, "vars": values}, {**select, "vars": values},
                   {"ansible.builtin.assert": {"that": [
                       "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'holonet_janitor_torrents') | list | length == expected"]},
                    "vars": {"expected": 1 if parent and enabled else 0}}]
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    # Execute the real torrents-only pre-write assertions without unrelated setup.
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
        (True, "agent-a", 1001, True, True),
        (True, "omarchy-pc", 1001, True, True),
    ]:
        checks += [{**guard, "vars": {"inventory_hostname": host, FLAG: flag, "ansible_facts": {"user_uid": uid},
                    "webmcp_interactive_holonet_writer_enabled": writer_enabled},
                    "ignore_errors": True, "register": "guard_result"},
                   {"ansible.builtin.assert": {"that": ["guard_result.failed | default(false) == refused"]},
                    "vars": {"refused": refused}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr
