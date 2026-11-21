"""Antigravity's JSON registrations preserve private and unrelated state."""
import json

import pytest

from test_mcp_registration import call, Failed


def test_registration_round_trip_and_check_mode(tmp_path):
    path = tmp_path / "gemini/config/mcp_config.json"
    path.parent.mkdir(parents=True)
    original = '{"keep": "https://example/a,b}", // comment\n "mcpServers": {"other": {"env": {"TOKEN": "private"}}, "local-file-llm": {},},}'
    path.write_text(original)
    params = {"antigravity_config": str(path), "name": "huyang",
              "command": "/opt/huyang", "args": ["mcp", "--profile", "full"],
              "env": {"OV_AGENT": "antigravity-host"},
              "extra": {"disabledTools": ["some_tool"]}}
    result = call("antigravity", check_mode=True, **params)
    assert result["changed"] and path.read_text() == original
    assert "antigravity-host" not in json.dumps(result)
    assert "private" not in json.dumps(result)
    assert call("antigravity", **params)["changed"]
    data = json.loads(path.read_text())
    assert data["keep"] == "https://example/a,b}"
    assert data["mcpServers"]["other"]["env"]["TOKEN"] == "private"
    assert data["mcpServers"]["huyang"] == {
        "command": params["command"], "args": params["args"],
        "env": params["env"], **params["extra"]}
    assert not call("antigravity", **params)["changed"]
    absent = {"antigravity_config": str(path), "name": "local-file-llm", "state": "absent"}
    assert call("antigravity", check_mode=True, **absent)["changed"]
    assert "local-file-llm" in json.loads(path.read_text())["mcpServers"]
    assert call("antigravity", **absent)["changed"]
    assert not call("antigravity", **absent)["changed"]


def test_ov_stdio_retirement_does_not_disable_antigravity():
    from pathlib import Path
    import yaml
    from jinja2 import Environment
    root = Path(__file__).resolve().parents[1]
    defaults = yaml.safe_load((root / "roles/mcp_registrations/defaults/main.yml").read_text())
    ov = next(s for s in defaults["mcp_registrations_servers"] if s["name"] == "ov-memory")
    assert ov["enabled_by_provider"] == {"antigravity": True}
    tasks = yaml.safe_load((root / "roles/mcp_registrations/tasks/main.yml").read_text())
    state = next(t["mcp_registration"]["state"] for t in tasks if "mcp_registration" in t)
    env = Environment()
    env.filters["bool"] = bool
    for provider, expected in [("antigravity", "present"), ("claude", "absent"), ("codex", "absent")]:
        assert env.from_string(state).render(item=[provider, {**ov, "enabled": False}]) == expected


def test_empty_config_written_by_agy_is_treated_as_missing(tmp_path):
    path = tmp_path / "gemini/config/mcp_config.json"
    path.parent.mkdir(parents=True)
    params = {"antigravity_config": str(path), "name": "huyang", "command": "/opt/huyang"}
    for empty in ("", "  \n"):
        path.write_text(empty)
        path.chmod(0o644)
        assert call("antigravity", check_mode=True, **params)["changed"]
        assert path.read_text() == empty
        assert call("antigravity", **params)["changed"]
        assert json.loads(path.read_text())["mcpServers"]["huyang"]["command"] == "/opt/huyang"
        assert path.stat().st_mode & 0o777 == 0o644
        assert not call("antigravity", **params)["changed"]


BRIDGE = "/usr/local/libexec/webmcp-stdio-bridge"
MANAGED = [("jocasta", "https://jocasta.mcp.ryzhkov.dev/mcp", None, ("laptop", "agent-a", "agent-b", "omarchy-pc")),
           ("ov", "https://ov.mcp.ryzhkov.dev/mcp", "ov-full", ("laptop", "omarchy-pc")),
           ("shizune", "https://shizune.mcp.ryzhkov.dev/mcp", None, ("laptop", "omarchy-pc"))]
SECRET = "Bearer SECRET-sentinel-a9e2"


def managed(path, name, url, profile, host, **change):
    params = {"antigravity_config": str(path), "name": name, "transport": "remote", "url": url,
              "auth_mode": "managed_helper", "helper_host": host}
    if profile is not None:
        params["helper_profile"] = profile
    return params | change


@pytest.mark.parametrize("name,url,profile,hosts", MANAGED)
def test_managed_entries_become_the_fixed_stdio_bridge(tmp_path, name, url, profile, hosts):
    path = tmp_path / "gemini/config/mcp_config.json"
    path.parent.mkdir(parents=True)
    # A hand-made remote entry with a static token is replaced, never shown.
    path.write_text(json.dumps({"keep": 1, "mcpServers": {
        "huyang": {"command": "/opt/huyang", "args": [], "env": {}},
        name: {"serverUrl": url, "headers": {"Authorization": SECRET}}}}))
    for host in hosts:
        params = managed(path, name, url, profile, host)
        result = call("antigravity", check_mode=True, **params)
        assert result["changed"] and SECRET not in json.dumps(result)
        result = call("antigravity", **params)
        assert SECRET not in json.dumps(result) and SECRET not in path.read_text()
        data = json.loads(path.read_text())
        assert data["keep"] == 1 and data["mcpServers"]["huyang"]["command"] == "/opt/huyang"
        assert data["mcpServers"][name] == {"command": BRIDGE, "args": [name, host], "env": {}}
        assert not call("antigravity", **params)["changed"]
    assert call("antigravity", **managed(path, name, url, profile, hosts[0], state="absent"))["changed"]
    assert name not in json.loads(path.read_text())["mcpServers"]


@pytest.mark.parametrize("change", [
    {"auth_mode": "oauth", "helper_host": None},  # Antigravity has no native OAuth form.
    {"helper_host": "normandy"}, {"helper_host": None},
    {"name": "shizune", "url": "https://shizune.mcp.ryzhkov.dev/mcp", "helper_host": "agent-a"},
    {"name": "ov", "url": "https://ov.mcp.ryzhkov.dev/mcp", "helper_host": "laptop"},  # narrow Codex-only OV
    {"name": "holonet_catalog", "url": "https://media.mcp.ryzhkov.dev/mcp", "helper_host": "laptop"},
    {"url": "https://other.example/mcp"}, {"extra": {"headers": {"Authorization": SECRET}}},
    {"extra": {"command": "/bin/sh"}}, {"command": "/bin/sh"}, {"args": ["jocasta", "laptop"]},
    {"env": {"TOKEN": SECRET}}, {"helper_profile": "ov-full"},
])
def test_antigravity_refuses_everything_but_the_closed_tuples(tmp_path, change):
    path = tmp_path / "mcp_config.json"
    path.write_text("{}")
    params = managed(path, "jocasta", "https://jocasta.mcp.ryzhkov.dev/mcp", None, "laptop") | change
    with pytest.raises(Failed) as failure:
        call("antigravity", **params)
    assert SECRET not in str(failure.value)
    assert path.read_text() == "{}"


def test_bridge_table_matches_the_module_tuples():
    from test_mcp_registration import module_code
    from test_webmcp_stdio_bridge import load_bridge
    bridge = load_bridge()
    assert module_code.BRIDGE_PATH == BRIDGE
    for name, url, profile, hosts in MANAGED:
        server = module_code.MANAGED_PROFILES[profile] if profile else module_code.MANAGED_SERVERS[name]
        assert "antigravity" in server["providers"]
        bridge_url, mode, bridge_hosts = bridge.SERVERS[name]
        assert bridge_url == server["url"] == url and set(bridge_hosts) == set(server["commands"]) == set(hosts)
        for host in hosts:
            assert server["commands"][host] == f"{bridge.HELPER} {mode} {host}"
    assert set(bridge.SERVERS) == {name for name, *_ in MANAGED}
    others = [s for key, s in module_code.MANAGED_SERVERS.items() if key not in ("jocasta", "shizune")]
    assert all("antigravity" not in server["providers"] for server in others)


def test_missing_config_and_unsafe_config(tmp_path):
    path = tmp_path / "new/mcp_config.json"
    params = {"antigravity_config": str(path), "name": "ov-memory", "command": "/opt/ov"}
    call("antigravity", check_mode=True, **params)
    assert not path.exists()
    call("antigravity", **params)
    assert path.stat().st_mode & 0o777 == 0o600
    for invalid in ('[]', '{"mcpServers": []}', '{"secret": "private", broken}'):
        path.write_text(invalid)
        with pytest.raises(Failed):
            call("antigravity", **params)
        assert path.read_text() == invalid
    path.unlink()
    target = tmp_path / "target"
    target.write_text("{}")
    path.symlink_to(target)
    with pytest.raises(Failed, match="regular file"):
        call("antigravity", **params)
    assert target.read_text() == "{}"
