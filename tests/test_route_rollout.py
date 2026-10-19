"""Routing inventory safety and OpenCode registration preservation."""
import json
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import call, Failed

ROOT = Path(__file__).resolve().parents[1]


def test_agent_clients_use_native_t3_quota():
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    common = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert set(hosts) == {"agent-a", "agent-b", "omarchy-pc", "laptop"}
    assert common["chaldea_client_version"] == "client-v0.4.2"
    assert common["chaldea_client_sha256"] == "40a00e518152f1d44251dc1bffddcea34ca613f43453a7dbf26ec890247c539a"
    # All agent hosts now use native T3 quota after approved local login checks.
    for name, values in hosts.items():
        assert "chaldea_client_version" not in values
        assert "chaldea_client_sha256" not in values
        effective = defaults | common | values
        assert effective["chaldea_client_enabled"] is True
        assert effective["chaldea_client_claude_usage_enabled"] is False
        assert effective["chaldea_client_version"] == "client-v0.4.2"
        assert effective["chaldea_client_quota_enabled"] is True
        assert effective["chaldea_client_codex_assert_runtime_home"] is True


def test_opencode_preserves_settings_check_mode_removal_and_mode(tmp_path):
    path = tmp_path / "opencode.json"
    original = {"model": "keep", "permission": {"edit": "ask"}, "instructions": ["keep.md"],
                "mcp": {"other": {"type": "remote", "url": "https://example.com"},
                        "chaldea": {"type": "local", "command": ["/old"],
                                    "environment": {"TOKEN": "old-secret"},
                                    "headers": {"Authorization": "old-header-secret"},
                                    "oauth": {"clientSecret": "old-oauth-secret"}}}}
    path.write_text(json.dumps(original))
    path.chmod(0o640)
    params = {"opencode_config": str(path), "name": "chaldea", "command": "/node",
              "args": ["/current/bin/chaldea", "mcp"], "env": {"TOKEN": "new-secret"}}
    check = call("opencode", check_mode=True, **params)
    assert check["changed"] and json.loads(path.read_text()) == original
    for secret in ("old-secret", "new-secret", "old-header-secret", "old-oauth-secret"):
        assert secret not in json.dumps(check)
    assert call("opencode", **params)["changed"]
    updated = json.loads(path.read_text())
    assert {k: v for k, v in updated.items() if k != "mcp"} == {k: v for k, v in original.items() if k != "mcp"}
    assert updated["mcp"]["other"] == original["mcp"]["other"]
    assert updated["mcp"]["chaldea"] == {"type": "local", "command": ["/node", "/current/bin/chaldea", "mcp"],
                                          "environment": {"TOKEN": "new-secret"}, "enabled": True}
    assert path.stat().st_mode & 0o777 == 0o640
    assert not call("opencode", **params)["changed"]
    assert call("opencode", state="absent", **params)["changed"]
    assert json.loads(path.read_text())["mcp"] == {"other": original["mcp"]["other"]}
    assert not call("opencode", state="absent", **params)["changed"]


@pytest.mark.parametrize("case", ["invalid", "mcp-list", "symlink", "jsonc"])
def test_opencode_refuses_ambiguous_configs(tmp_path, case):
    path = tmp_path / "opencode.json"
    path.write_text("invalid" if case == "invalid" else '{"mcp": []}' if case == "mcp-list" else '{}')
    if case == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    if case == "jsonc":
        path.with_suffix(".jsonc").write_text("// operator-owned")
    before = path.read_bytes()
    with pytest.raises(Failed):
        call("opencode", opencode_config=str(path), name="chaldea", command="/node")
    assert path.read_bytes() == before
