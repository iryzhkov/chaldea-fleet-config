"""Collector role stays inert until explicit deployment enablement."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_collector_is_disabled_and_uses_one_locked_scoped_service():
    defaults = yaml.safe_load((ROOT / "roles/akasha_collector/defaults/main.yml").read_text())
    assert defaults["akasha_collector_enabled"] is False
    assert defaults["akasha_collector_token_helper"] == ""
    service = (ROOT / "roles/akasha_collector/templates/akasha-collector.service.j2").read_text()
    assert "flock --nonblock" in service
    assert "AKASHA_TOKEN_HELPER" in service and "UnsetEnvironment=FEED_TOKEN" in service
    assert "feed/key" not in service
    for file in (ROOT / "inventory").rglob("*.yml"):
        assert "akasha_collector_enabled: true" not in file.read_text()


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
