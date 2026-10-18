"""Capacity is pending evidence; a missing executable is a missing server."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fleet_health", ROOT / "roles/huyang/files/huyang_health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class Client:
    def __init__(self, capacities):
        self.capacities = capacities
        self.status_calls = 0

    def call(self, name, _arguments):
        if name == "workspace_open":
            return {"outcome": "ok"}
        if name == "workspace_inspect":
            return {"outcome": "ok", "data": {"semantic_provider": {"state": "healthy"}}}
        self.status_calls += 1
        if self.status_calls <= self.capacities:
            return {"outcome": "failed", "code": "semantic_provider_start_failed",
                    "summary": "semantic provider capacity exhausted", "data": None}
        return {"outcome": "ok", "data": {"language_servers": {"languages": [
            {"filetype": "go", "lsp": "gopls", "attach": "attached"}]}}}


def test_transient_capacity_is_retried_without_missing_server_claim(monkeypatch):
    monkeypatch.setattr(health.time, "sleep", lambda _seconds: None)
    client = Client(1)
    result = health.probe_language(client, {"root": "/controlled/go"}, "go")
    assert result["attach"] == "attached" and client.status_calls == 2


def test_persistent_capacity_defers_runtime_evidence_without_failing(monkeypatch):
    monkeypatch.setattr(health.time, "sleep", lambda _seconds: None)
    client = Client(100)
    result = health.probe_language(client, {"root": "/controlled/go"}, "go")
    assert result == {"language": "go", "server": "gopls", "attach": "deferred_capacity"}
    assert client.status_calls == 3


def test_missing_required_executable_is_rejected_even_if_lspconfig_exists(tmp_path):
    with pytest.raises(ValueError, match="missing required server executable"):
        health.require_executables(str(tmp_path), ["go"])
    binary = tmp_path / "gopls"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o644)
    with pytest.raises(ValueError, match="missing required server executable"):
        health.require_executables(str(tmp_path), ["go"])
    binary.chmod(0o755)
    health.require_executables(str(tmp_path), ["go"])
