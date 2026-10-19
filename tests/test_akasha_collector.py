"""Collector role stays inert until explicit deployment enablement."""
import json
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_collector_is_disabled_and_uses_one_locked_scoped_service():
    defaults = yaml.safe_load((ROOT / "roles/akasha_collector/defaults/main.yml").read_text())
    assert defaults["akasha_collector_enabled"] is False
    assert defaults["akasha_collector_token_helper"] == ""
    service = (ROOT / "roles/akasha_collector/templates/akasha-collector.service.j2").read_text()
    assert "flock --nonblock" in service
    timer = (ROOT / "roles/akasha_collector/templates/akasha-collector.timer.j2").read_text()
    settings = dict(line.split("=", 1) for line in timer.splitlines() if "=" in line)
    assert settings["OnUnitInactiveSec"] == "5s"
    assert settings["RandomizedDelaySec"] == "1s"
    assert settings["AccuracySec"] == "1s"
    assert "AKASHA_TOKEN_HELPER" in service and "UnsetEnvironment=FEED_TOKEN" in service
    assert "feed/key" not in service
    normal = ROOT / "inventory/hosts.yml"
    hosts = yaml.safe_load(normal.read_text())["all"]["children"]["agent_hosts"]["hosts"]
    approved = {"agent-a", "agent-b", "omarchy-pc", "laptop"}
    assert {host for host, values in hosts.items() if values.get("akasha_collector_enabled")} == approved
    for host in approved:
        assert hosts[host]["akasha_collector_url"] == "https://akasha.ryzhkov.dev"
        assert hosts[host]["akasha_collector_token_helper"] == "/usr/local/bin/chaldea-token-helper"
    for file in (ROOT / "inventory").rglob("*.yml"):
        if file != normal:
            assert "akasha_collector_enabled: true" not in file.read_text()


def test_shared_collector_selection_preserves_enrollment_inventory():
    def hostvars(inventory):
        result = subprocess.run(
            ["ansible-inventory", "-i", inventory, "--list"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)["_meta"]["hostvars"]

    normal = hostvars("inventory/hosts.yml")
    for host in ("agent-a", "agent-b", "omarchy-pc", "laptop"):
        assert normal[host]["akasha_collector_version"] == "host-v0.2.6"
        assert normal[host]["chaldea_host_version"] == "host-v0.2.2"
        assert normal[host]["pull_timer_enabled"] is True
        assert normal[host]["retention_timer_enabled"] is True
    for values in hostvars("inventory/akasha-enrollment.yml").values():
        assert "akasha_collector_version" not in values
        assert "akasha_collector_script" not in values


def test_timer_reporting_uses_artifact_and_delivery_configuration():
    tasks = yaml.safe_load((ROOT / "roles/timer_reporting/tasks/main.yml").read_text())
    includes = [t["ansible.builtin.include_role"]["name"] for t in tasks if "ansible.builtin.include_role" in t]
    assert includes == ["chaldea_host_artifact", "akasha_collector"]
    wrapper = next(t for t in tasks if t["name"] == "Install the timer outcome wrapper")
    assert wrapper["ansible.builtin.copy"]["src"] == "{{ chaldea_host_artifact_root }}/chaldea-timer-report"
    assert wrapper["ansible.builtin.copy"]["remote_src"] is True
    config = next(t["ansible.builtin.copy"] for t in tasks if t["name"] == "Configure timer outcome delivery")
    assert "'queue' if akasha_collector_enabled" in config["content"]
    assert "else 'feed'" in config["content"]
    assert config["dest"].endswith("/.config/chaldea/timer-reporting.json")
