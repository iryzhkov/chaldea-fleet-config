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


def test_timer_reporting_includes_collector_and_has_no_network_delivery():
    tasks = yaml.safe_load((ROOT / "roles/timer_reporting/tasks/main.yml").read_text())
    assert tasks[0]["ansible.builtin.include_role"]["name"] == "akasha_collector"
    script = (ROOT / "roles/akasha_collector/files/chaldea-timer-report").read_text()
    enqueue = script[script.index("def queue_delivery"):script.index("def record_outcome")]
    assert "subprocess." not in enqueue
    assert "8 * 1024 * 1024" in enqueue and "dropped" in enqueue
