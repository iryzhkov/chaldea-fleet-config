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
