"""Fixed same-account seed_join registration, isolated from writer and reader."""
import json
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet_writer import writer
from test_webmcp_managed_holonet_janitor import janitor
from test_webmcp_managed_holonet_torrents import torrents
from test_webmcp_managed_holonet import reader, _ansible
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
FLAG = "webmcp_interactive_holonet_seed_join_enabled"
URL = "https://media.mcp.ryzhkov.dev/mcp"
HELPER = "/usr/local/libexec/webmcp-interactive-headers holonet-seed-join laptop"


def seed_join(**changes):
    return {"name": "holonet_janitor_seed_join", "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": "laptop"} | changes


def test_seed_join_codex_repeat_and_inverse_preserve_writer_reader(tmp_path):
    path = tmp_path / "config.toml"
    call("codex", codex_config=str(path), **reader())
    call("codex", codex_config=str(path), **writer())
    call("codex", codex_config=str(path), **janitor())
    call("codex", codex_config=str(path), **torrents())
    before = tomllib.loads(path.read_text())
    assert call("codex", codex_config=str(path), **seed_join())["changed"]
    assert tomllib.loads(path.read_text())["mcp_servers"]["holonet_janitor_seed_join"]["http_headers_helper"] == HELPER
    assert not call("codex", codex_config=str(path), **seed_join())["changed"]
    assert call("codex", codex_config=str(path), **seed_join(state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


def test_seed_join_claude_preserves_neighbors(tmp_path):
    path = tmp_path / "claude.json"
    before = {"mcpServers": {"other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    args = {"claude_config": str(path),
            "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", **args, **seed_join())["changed"]
    assert not call("claude", **args, **seed_join())["changed"]
    assert call("claude", **args, **seed_join(state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("provider,change", [
    ("opencode", {}), ("codex", {"helper_host": "agent-a"}),
    ("claude", {"helper_host": "omarchy-pc"}), ("codex", {"url": URL + "/"}),
    ("codex", {"extra": {"headers": {"Authorization": "synthetic"}}}),
    ("claude", {"helper_profile": "ov-full"}),
    ("codex", {"extra": {"http_headers_helper": HELPER + " extra"}}),
    ("claude", {"extra": {"headersHelper": HELPER.replace("holonet-seed-join", "holonet-janitor")}}),
])
def test_seed_join_closed_registration(provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider, {"extra": {}, **seed_join(**change)})


def test_seed_join_default_off_and_real_selection(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    activation = ROOT / "inventory/host_vars/laptop/holonet-interactive.yml"
    laptop = yaml.safe_load(activation.read_text())
    assert laptop[FLAG] is True
    assert laptop["webmcp_interactive_holonet_torrents_enabled"] is True
    assert laptop["webmcp_interactive_holonet_janitor_enabled"] is True
    assert laptop["webmcp_interactive_holonet_writer_enabled"] is True
    assert all(FLAG not in p.read_text() for p in (ROOT / "inventory").rglob("*.yml") if p != activation)
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    select = next(t for t in tasks if t["name"] == "Select the closed laptop HoloNet seed_join on explicit opt-in")
    base, _ = selection_tasks()
    checks = []
    for parent, enabled in [(True, False), (True, True), (False, True)]:
        values = {"webmcp_interactive_enabled": parent, FLAG: enabled,
                  "webmcp_interactive_holonet_torrents_enabled": False,
                  "mcp_registrations_remote_servers": [reader(), writer(), janitor()]}
        checks += [{**base, "vars": values}, {**select, "vars": values},
                   {"ansible.builtin.assert": {"that": [
                       "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'holonet_janitor_seed_join') | list | length == expected"]},
                    "vars": {"expected": 1 if parent and enabled else 0}}]
    role = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    # Execute the real seed_join-only pre-write assertions without unrelated setup.
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
