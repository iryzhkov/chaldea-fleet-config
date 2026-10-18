"""Exercise the approved one-host config through the real role, fake credentials only."""
import json
from pathlib import Path

import yaml

from test_chaldea_client import ROOT, fixture, provision, run, success


def test_omarchy_reader_and_conservative_pins(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    host = inventory["all"]["children"]["agent_hosts"]["hosts"]["omarchy-pc"]
    assert host["chaldea_client_version"] == "client-v0.4.1"
    assert host["chaldea_client_sha256"] == "86ee3bda7a5f78fa4c93b5e7ae945f0c96f9244be4a6d02c235957e4da282cdb"
    for key in ("chaldea_client_claude_usage_enabled", "chaldea_client_claude_usage_source",
                "chaldea_client_claude_contexts", "chaldea_client_route_targets"):
        variables[key] = host[key]
    variables["chaldea_client_quota_enabled"] = True
    provision()
    success(run(tmp_path, variables))
    home = Path.home()
    route = json.loads((home / ".config/chaldea/route.json").read_text())
    quota = json.loads((home / ".config/chaldea/quota.json").read_text())
    source = {"enabled": True, "providerInstanceId": "claudeAgent",
              "envFile": str(home / ".config/claude/oauth.env"),
              "envVar": "CLAUDE_CODE_OAUTH_TOKEN"}
    assert route["claudeUsage"] == source
    assert quota["claudeContexts"] == [source]
    assert route["scores"] == {"enabled": False}
    assert route["pins"] == {
        "builder": {"model": "gpt-6.1-sol", "providerInstanceId": "codex"},
        "bulk-read": {"model": "gpt-6-luna", "providerInstanceId": "codex"},
        "general": {"model": "gpt-6.1-sol", "providerInstanceId": "codex"},
    }
    assert "critical-review" not in route["pins"]
    assert "fleet" not in quota
    assert not (home / ".config/claude/oauth.env").exists(), "role must never create credentials"
    repeated = run(tmp_path, variables)
    success(repeated)
    assert "changed=0" in repeated.stdout


def test_old_client_refuses_reader_config_before_writes(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch, version="client-v0.3.0")
    variables["chaldea_client_claude_usage_source"] = {
        "envFile": str(Path.home() / ".config/claude/oauth.env")}
    result = run(tmp_path, variables)
    assert result.returncode != 0
    assert not (Path.home() / ".local/share/chaldea").exists()
    assert not (tmp_path / "systemctl.json").read_text().count('"restart"')
