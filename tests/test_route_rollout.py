"""Routing inventory safety and OpenCode registration preservation."""
import json
import re
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
    assert common["chaldea_client_version"] == "client-v0.4.23"
    assert common["chaldea_client_sha256"] == "b96c928d050d81e7be96841baf8ce0204927cd14fbd43b62cc0d4ac058fb9c82"
    # All agent hosts now use native T3 quota after approved local login checks.
    for name, values in hosts.items():
        assert "chaldea_client_version" not in values
        assert "chaldea_client_sha256" not in values
        effective = defaults | common | values
        assert effective["chaldea_client_enabled"] is True
        assert effective["chaldea_client_claude_usage_enabled"] is False
        assert effective["chaldea_client_version"] == "client-v0.4.23"
        assert effective["chaldea_client_quota_enabled"] is True
        assert effective["chaldea_client_codex_assert_runtime_home"] is True


# Reviewed host-level release selections, by exact file and top-level key. The
# laptop's persistent system waits run a separately installed runtime with its
# Node, and its fixed profiles pin staged native assets by hash. Their exact
# values are asserted in test_laptop_jocasta_tooling.py.
# The held laptop OV activation pins the reviewed aarch64 headers helper for
# the laptop alone; its exact value is asserted in
# test_webmcp_managed_interactive.py. The default-off HoloNet catalog profile
# pins the same staged Claude native; its values are asserted in
# test_laptop_holonet_catalog.py.
# The laptop and omarchy-pc stdio OV safety pins are checked for every host in
# test_ov_source_selection.py.
HOST_RELEASE_SELECTIONS = {
    "inventory/host_vars/omarchy-pc/fate-route.yml": frozenset({"chaldea_client_version", "chaldea_client_sha256"}),
    "inventory/host_vars/laptop/ov-memory.yml": frozenset({"agent_tools_ov_memory_ref"}),
    "inventory/host_vars/omarchy-pc/ov-memory.yml": frozenset({
        "agent_tools_ov_memory_ref", "webmcp_interactive_helper_sha256"}),
    "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml": frozenset({
        "chaldea_node_version", "chaldea_client_waits_legacy_user_node_version",
        "chaldea_client_waits_runtime_root",
        "chaldea_laptop_jocasta_profiles"}),
    "inventory/host_vars/laptop/chaldea-holonet-catalog.yml": frozenset({"chaldea_laptop_holonet_catalog_profiles"}),
    "inventory/host_vars/laptop/jocasta-interactive.yml": frozenset({"webmcp_interactive_helper_sha256"}),
    # Inactive-runtime retention only; bounded histories and cleanup preservation
    # are exercised in test_chaldea_client.py. These do not select active pins.
    "inventory/host_vars/agent-a/chaldea-staging-retention.yml": frozenset({"chaldea_client_retained_versions"}),
    "inventory/host_vars/agent-b/chaldea-staging-retention.yml": frozenset({"chaldea_client_retained_versions"}),
    "inventory/host_vars/omarchy-pc/chaldea-staging-retention.yml": frozenset({"chaldea_client_retained_versions"}),
}


def test_host_settings_do_not_override_shared_software_releases():
    def check(values, location, allowed=frozenset()):
        if isinstance(values, dict):
            for key, value in values.items():
                # Retention records keep rollback artifacts, not desired releases.
                if key == "chaldea_host_artifact_preserve_versions" or key in allowed:
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
        relative = path.relative_to(ROOT).as_posix()
        values = yaml.safe_load(path.read_text())
        allowed = HOST_RELEASE_SELECTIONS.get(relative, frozenset())
        assert allowed <= set(values), relative
        check(values, relative, allowed)
    for relative in HOST_RELEASE_SELECTIONS:
        assert (ROOT / relative).is_file(), relative


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
