"""Routing inventory safety and OpenCode registration preservation."""
import json
import re
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import call, Failed

ROOT = Path(__file__).resolve().parents[1]

# The approved coordinated runtime exception is exact and limited to omarchy-pc.
OMARCHY_RUNTIME_PINS = {
    "t3_version": "0.0.45",
    "t3_required_binary_sha256": "18c808e79a4c84ba64e0ef1e064de94838f22789f0dc650e8b5cddff33dae495",
    "t3_custom_source": "161de7bb3e948490fd8af5b0da16c034067a5685",
    "t3_custom_archive_sha256": "ad50546a2bce82ae04b8fd57cc75e9df97bdd3965dc5c7a08320904ba4bee403",
    "chaldea_client_version": "client-v0.4.17",
    "chaldea_client_sha256": "81a1c1860ff3194a288fa4518bfca3e46dbc732ee23c872aebb6382afbd50839",
}


def test_agent_clients_use_native_t3_quota():
    defaults = yaml.safe_load((ROOT / "roles/chaldea_client/defaults/main.yml").read_text())
    common = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert set(hosts) == {"agent-a", "agent-b", "omarchy-pc", "laptop"}
    assert common["chaldea_client_version"] == "client-v0.4.11"
    assert common["chaldea_client_sha256"] == "e9ae469524ecd4498801a3386c1aeb0d3d317b821fe98fbdf510c532c4a3c006"
    # All agent hosts now use native T3 quota after approved local login checks.
    for name, values in hosts.items():
        if name == "omarchy-pc":
            assert {key: values[key] for key in OMARCHY_RUNTIME_PINS} == OMARCHY_RUNTIME_PINS
        else:
            assert "chaldea_client_version" not in values
            assert "chaldea_client_sha256" not in values
        effective = defaults | common | values
        assert effective["chaldea_client_enabled"] is True
        assert effective["chaldea_client_claude_usage_enabled"] is False
        expected = OMARCHY_RUNTIME_PINS if name == "omarchy-pc" else common
        assert effective["chaldea_client_version"] == expected["chaldea_client_version"]
        assert effective["chaldea_client_sha256"] == expected["chaldea_client_sha256"]
        assert effective["chaldea_client_quota_enabled"] is True
        assert effective["chaldea_client_codex_assert_runtime_home"] is True


def test_host_settings_do_not_override_shared_software_releases():
    def check(values, location):
        if isinstance(values, dict):
            for key, value in values.items():
                if location == "omarchy-pc" and key in OMARCHY_RUNTIME_PINS:
                    assert value == OMARCHY_RUNTIME_PINS[key], (location, key)
                    continue
                # Retention records keep rollback artifacts, not desired releases.
                if key == "chaldea_host_artifact_preserve_versions":
                    continue
                assert not re.search(r"(^|_)(versions?|sha256|checksums?|revision|commit|ref|build|release)(_|$)", key), (location, key)
                check(value, f"{location}.{key}")
        elif isinstance(values, list):
            for value in values:
                check(value, location)
        elif isinstance(values, str):
            assert not re.search(r"/(releases|builds)/|/installs/[^/]+/[0-9]", values), (location, values)

    def group(node):
        for host, values in node.get("hosts", {}).items():
            check(values or {}, host)
        for child in node.get("children", {}).values():
            group(child)

    group(yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"])
    for path in (ROOT / "inventory/host_vars").rglob("*.yml"):
        check(yaml.safe_load(path.read_text()), str(path))


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
