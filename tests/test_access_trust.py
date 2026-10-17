"""Trust packaging contracts; no real services or keys."""
import base64
import hashlib
import json
from pathlib import Path

from jinja2 import Environment, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_access_trust"


def test_inventory_disabled_and_units_use_isolated_state():
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())
    assert defaults["chaldea_access_trust_enabled"] is False
    assert inventory["chaldea_access_trust_enabled"] is False
    anchor = inventory["chaldea_access_trust_anchors"][0]
    assert anchor == {"kid": "deployment-2026-10", "public_key": {
        "kty": "OKP", "crv": "Ed25519", "x": "re7EPlrspBhs_OHsN7z1VqDZ8HkVib4glgZCczaKjRc"}}
    spki = bytes.fromhex("302a300506032b6570032100") + base64.urlsafe_b64decode(anchor["public_key"]["x"] + "=")
    assert hashlib.sha256(spki).hexdigest() == "222450438cdcae5bda6c498f5e39baee5e2479923389c28e518ccf9138aee296"
    variables = defaults | {
        "chaldea_access_paths": {"clock_health": "/scratch/run/clock-health.json"},
        "chaldea_access_trust_fetcher": "/scratch/fetch",
        "chaldea_access_trust_root": "/scratch/config",
        "chaldea_access_trust_state": "/scratch/state",
        "chaldea_access_trust_public": "/scratch/public",
        "chaldea_access_trust_run": "/scratch/run",
    }
    env = Environment(undefined=StrictUndefined)
    units = {}
    for path in (ROLE / "templates").glob("*.service.j2"):
        units[path.name] = env.from_string(path.read_text()).render(variables)
    updater = units["chaldea-access-trust.service.j2"]
    assert "User=root" in updater and "NoNewPrivileges=true" in updater
    assert "ProtectHome=true" in updater and "ProtectSystem=strict" in updater
    assert "ReadWritePaths=/scratch/state /scratch/public" in updater
    assert "TMPDIR=/scratch/state" in updater
    timer = (ROLE / "templates/chaldea-access-trust.timer.j2").read_text()
    assert "OnUnitActiveSec=120s" in timer
    clock = units["chaldea-clock-health.service.j2"]
    assert "clock-health --output /scratch/run/clock-health.json" in clock
    assert "RuntimeDirectoryPreserve=yes" in clock
    assert "ReadWritePaths=/scratch/run -/run/chrony" in clock
    assert "--check-runtime" in clock
    tasks = (ROLE / "tasks/main.yml").read_text()
    assert "initialize-state" not in tasks and "genpkey" not in tasks
    keys = json.loads((ROOT / "access-trust/issuer-grants.json").read_text())
    assert len(keys) == 1
    key = keys[0]
    assert (key["issuer"], key["kid"]) == ("chaldea:agent-a", "agent-a-2026-10")
    assert key["public_key"] == {"kty": "OKP", "crv": "Ed25519", "x": "1LEmYnODsGqzGLbE_F5uqOx1VoY5I2EmJSbLAKMJtCM"}
    assert key["not_before"] == 1792195200
    assert key["issue_until"] - key["not_before"] == 30 * 86400
    assert key["verify_until"] - key["issue_until"] == 810
    assert {(c["profile"], c["project"], c["source"]) for c in key["ceilings"]} == {
        ("daily-health", "homelab", "chaldea.daily-health.agent-a"),
        ("fleet-timers", "chaldea", "agent-a.fleet"),
        ("toolfeedback", "chaldea", "agent-a.toolfeedback"),
    }
    for ceiling in key["ceilings"]:
        assert ceiling["audience"] == "akasha"
        assert ceiling["grants"] == [{"resource": ceiling["source"], "actions": ["append"]}]


def test_updater_paths_are_one_consistent_fetch_and_unit_contract():
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    validate = next(t for t in tasks if t["name"] == "Validate explicit trust enrollment")
    conditions = [c for c in validate["ansible.builtin.assert"]["that"] if "chaldea_access_paths." in c]
    assert len(conditions) == 3
    paths = inventory["chaldea_access_paths"]
    values = {
        "chaldea_access_paths": paths,
        "chaldea_access_trust_state": paths["state"],
        "chaldea_access_trust_public": paths["public"],
        "chaldea_access_trust_run": paths["run"],
    }
    env = Environment(undefined=StrictUndefined)
    expressions = [env.compile_expression(c) for c in conditions]
    assert all(expression(**values) for expression in expressions)
    for key in ("updater_state", "bundle", "clock_health"):
        inconsistent = values | {"chaldea_access_paths": paths | {key: "/wrong/path"}}
        assert not all(expression(**inconsistent) for expression in expressions)
