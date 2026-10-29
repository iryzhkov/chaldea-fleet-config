"""The approved FATE canary changes exactly two route scopes and one client."""
import json
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLIENT_SHA = "61213c3347c23d45604196cfc47853a1161de4bc4a2f88068905e916237f49e4"


def test_signed_route_ceilings_are_only_homelab_append_and_pc_read():
    issuers = json.loads((ROOT / "access-trust/issuer-grants.json").read_text())
    actual = [(row["issuer"], ceiling) for row in issuers
              for ceiling in row["ceilings"] if ceiling["source"] == "route"]
    assert actual == [
        ("chaldea:omarchy-pc", dict(audience="akasha", profile="route-service",
            project="chaldea", source="route", grants=[dict(resource="route", actions=["read"])])),
        ("chaldea:homelab", dict(audience="akasha", profile="route-service",
            project="chaldea", source="route", grants=[dict(resource="route", actions=["append"])])),
    ]


def test_helper_additions_bind_exact_uid_host_kind_and_action():
    additions = json.loads((ROOT / "access-trust/fate-route-helper-additions.json").read_text())
    assert set(additions) == {"homelab", "omarchy-pc"}
    for host, uid, action in [("homelab", 0, "append"), ("omarchy-pc", 1000, "read")]:
        assert additions[host] == [dict(uid=uid, audience="akasha", action=action,
            source="route", host=host, kind="route_score_snapshot",
            profile="route-service", project="chaldea")]


def test_actual_inventory_limits_client_and_score_transport_to_pc():
    result = subprocess.run(["ansible-inventory", "-i", str(ROOT / "inventory/hosts.yml"), "--list"],
                            check=True, text=True, capture_output=True)
    hosts = json.loads(result.stdout)["_meta"]["hostvars"]
    for host in ["agent-a", "agent-b", "laptop", "omarchy-pc"]:
        values = hosts[host]
        assert values["chaldea_client_version"] == (
            "client-v0.4.22" if host == "omarchy-pc" else "client-v0.4.11")
        if host != "omarchy-pc":
            assert not values.get("chaldea_client_route_targets", {}).get("scores", {}).get("enabled", False)
    pc = hosts["omarchy-pc"]
    assert pc["chaldea_client_sha256"] == CLIENT_SHA
    targets = pc["chaldea_client_route_targets"]
    assert targets == dict(
        scores=dict(enabled=True, url="https://akasha.ryzhkov.dev",
                    tokenHelper="/usr/local/bin/chaldea-token-helper", host="omarchy-pc"),
        announceHost="homelab", pins={},
        benchmark=dict(indexVersion="5", anchors={
            "bulk-read": ["gpt-6.1-sol", "claude-opus-5-5"],
            "critical-review": ["gpt-6.1-sol", "claude-opus-5-5"]}))
    assert pc["chaldea_job_client_exec_entry"].endswith(
        "client-1e86175cd2ef2e11fdf4584d22cc73127a162d42/bin/chaldea")


def test_baseline_floors_and_default_release_are_not_lowered():
    common = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    assert common["chaldea_client_version"] == "client-v0.4.11"
    targets = yaml.safe_load((ROOT / "inventory/host_vars/omarchy-pc/fate-route.yml").read_text())[
        "chaldea_client_route_targets"]
    assert "floors" not in targets
