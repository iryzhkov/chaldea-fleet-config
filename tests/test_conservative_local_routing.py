"""Exercise the approved one-host config through the real role, fake credentials only."""
import json
from pathlib import Path

import yaml

from test_chaldea_client import ROOT, fixture, provision, run, success


def test_omarchy_native_quota_reader_uses_unpinned_role_policy(tmp_path, monkeypatch):
    variables = fixture(tmp_path, monkeypatch)
    inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    common = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    host = common | inventory["all"]["children"]["agent_hosts"]["hosts"]["omarchy-pc"]
    assert host["chaldea_client_version"] == "client-v0.4.17"
    assert host["chaldea_client_sha256"] == "81a1c1860ff3194a288fa4518bfca3e46dbc732ee23c872aebb6382afbd50839"
    for key in ("chaldea_client_claude_usage_enabled", "chaldea_client_claude_usage_source",
                "chaldea_client_claude_contexts", "chaldea_client_route_targets",
                "chaldea_client_analytics_max_age_ms"):
        variables[key] = host[key]
    variables["chaldea_client_quota_enabled"] = True
    legacy_credential = Path.home() / ".config/claude/oauth.env"
    legacy_credential.parent.mkdir(parents=True)
    legacy_credential.write_text("PRIVATE-LEGACY-SENTINEL")
    legacy_credential.chmod(0o600)
    provision()
    success(run(tmp_path, variables))
    home = Path.home()
    route = json.loads((home / ".config/chaldea/route.json").read_text())
    quota = json.loads((home / ".config/chaldea/quota.json").read_text())
    assert route["claudeUsage"] == {"enabled": False, "providerInstanceId": "claudeAgent"}
    assert "claudeContexts" not in quota
    assert route["scores"] == {"enabled": False}
    assert route["analyticsMaxAgeMs"] == 7776000000
    assert route["pins"] == {}
    assert route["failureMargin"] == 0.10
    assert route["minimumTurns"] == 100
    assert "fleet" not in quota
    assert legacy_credential.read_text() == "PRIVATE-LEGACY-SENTINEL"
    assert legacy_credential.stat().st_mode & 0o777 == 0o600
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
