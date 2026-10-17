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
    assert inventory["chaldea_access_trust_repository"] == "ssh://git@github.com/iryzhkov/chaldea-trust.git"
    assert inventory["chaldea_access_trust_bundle_path"] == "bundle.jws"
    assert not (ROOT / "access-trust/bundle.jws").exists()
    fetch_copy = next(t["ansible.builtin.copy"] for t in yaml.safe_load(
        (ROLE / "tasks/main.yml").read_text()) if t["name"] == "Install byte-only Git downloader")
    assert fetch_copy["src"] == "{{ chaldea_host_artifact_root }}/chaldea-access-trust-fetch"
    assert fetch_copy["remote_src"] is True
    assert not (ROLE / "files/chaldea-access-trust-fetch").exists()
    env = Environment(undefined=StrictUndefined)
    env.filters["to_nice_json"] = json.dumps
    config_vars = inventory | defaults | {
        "chaldea_access_trust_state": "/scratch/state",
        "chaldea_access_trust_root": "/scratch/config",
        "chaldea_access_trust_runtime": "/scratch/runtime",
        "chaldea_access_trust_ssh_key": "/scratch/read-key",
        "chaldea_access_trust_known_hosts": "/scratch/known_hosts"}
    updater_config = json.loads(env.from_string((ROLE / "templates/updater.json.j2").read_text()).render(config_vars))
    assert updater_config["repository"] == inventory["chaldea_access_trust_repository"]
    assert updater_config["bundle_path"] == "bundle.jws"
    # A source placeholder cannot become a valid public pin by accident.
    assert inventory["chaldea_deployment_anchor_kid"] == "deployment-2026-10b"
    key = inventory["chaldea_deployment_anchor_public_jwk"]
    assert key["kty"] == "OKP" and key["crv"] == "Ed25519"
    if key["x"].startswith("REPLACE_"):
        assert key["x"] == "REPLACE_WITH_NORMANDY_PUBLIC_JWK_X"
        assert inventory["chaldea_deployment_anchor_spki_sha256"] == "REPLACE_WITH_NORMANDY_SPKI_SHA256"
    else:
        spki = bytes.fromhex("302a300506032b6570032100") + base64.urlsafe_b64decode(key["x"] + "=")
        assert hashlib.sha256(spki).hexdigest() == inventory["chaldea_deployment_anchor_spki_sha256"]
    assert inventory["chaldea_access_trust_anchors"] == [{
        "kid": "{{ chaldea_deployment_anchor_kid }}",
        "public_key": "{{ chaldea_deployment_anchor_public_jwk }}"}]
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
