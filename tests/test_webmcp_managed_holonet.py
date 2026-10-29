"""Closed ordinary laptop HoloNet reader; synthetic configs and metadata only."""
import copy
import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import Failed, FakeModule, call, module_code
from test_mcp_remote_registration import CODEX_CONFIG, SECRET
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
URL = "https://media.mcp.ryzhkov.dev/mcp"
HELPER = "/usr/local/libexec/webmcp-interactive-headers holonet laptop"
FLAG = "webmcp_interactive_holonet_enabled"


def reader(**change):
    return dict(name="holonet_catalog", transport="remote", url=URL,
                auth_mode="managed_helper", helper_host="laptop") | change


def test_closed_holonet_tuple_and_native_config_inverse_preserve_neighbors(tmp_path):
    assert module_code.MANAGED_SERVERS["holonet_catalog"] == {
        "url": URL, "providers": frozenset({"codex"}), "commands": {"laptop": HELPER}}
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG)
    before = tomllib.loads(path.read_text())
    preview = call("codex", check_mode=True, codex_config=str(path), **reader())
    assert preview["changed"] and tomllib.loads(path.read_text()) == before
    result = call("codex", codex_config=str(path), **reader())
    assert result["changed"] and SECRET not in json.dumps(result)
    actual = tomllib.loads(path.read_text())
    assert actual["mcp_servers"]["holonet_catalog"] == {"url": URL, "http_headers_helper": HELPER}
    assert {k: v for k, v in actual["mcp_servers"].items() if k != "holonet_catalog"} == before["mcp_servers"]
    assert not call("codex", codex_config=str(path), **reader())["changed"]
    assert call("codex", codex_config=str(path), **reader(state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == before


@pytest.mark.parametrize("change", [
    {"helper_host": "agent-a"}, {"helper_host": "omarchy-pc"}, {"helper_host": None},
    {"name": "holonet"}, {"name": "Holonet_catalog"}, {"url": URL + "/"},
    {"url": "http://media.mcp.ryzhkov.dev/mcp"},
    {"url": "https://jocasta.mcp.ryzhkov.dev/mcp"},
    {"extra": {"http_headers": {"Authorization": SECRET}}},
    {"extra": {"http_headers_helper": HELPER + " --user=other"}},
    {"extra": {"scopes": ["holonet.read"]}},
])
def test_holonet_tuple_drift_refuses_before_native_write(tmp_path, change):
    path = tmp_path / "config.toml"
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), **reader(**change))
    assert not path.exists()


def test_holonet_does_not_select_other_native_clients(tmp_path):
    for provider, field in (("claude", "claude_config"), ("opencode", "opencode_config")):
        path = tmp_path / (provider + ".json")
        with pytest.raises(Failed):
            module_code.remote_definition(FakeModule(False), provider, {"extra": {}, **reader()})
        assert not path.exists()


def _ansible(tmp_path, tasks):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    path = tmp_path / "proof.yml"
    path.write_text(yaml.safe_dump([{"hosts": "laptop", "connection": "local", "gather_facts": False,
                                    "tasks": tasks}]))
    return subprocess.run(["ansible-playbook", "-i", "laptop,", str(path)], capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def test_actual_selection_defaults_off_preserves_entries_and_absent_intent(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    owner = ROOT / "inventory/host_vars/laptop/holonet-interactive.yml"
    assert yaml.safe_load(owner.read_text()) == {FLAG: True}
    for path in (ROOT / "inventory").rglob("*.yml"):
        assert (FLAG in path.read_text(errors="replace")) is (path == owner)
    jocasta, _ = selection_tasks()
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    selection = next(t for t in tasks if t["name"].startswith("Select the closed laptop HoloNet"))
    unrelated = {"name": "other", "url": "https://other.invalid/mcp", "providers": ["codex"]}
    target = {"name": "holonet_catalog", "url": URL, "providers": ["codex"],
              "auth_mode": "managed_helper", "helper_host": "laptop", "state": "present"}
    fixed_jocasta = {"name": "jocasta", "url": "https://jocasta.mcp.ryzhkov.dev/mcp",
                     "providers": ["claude", "codex"], "auth_mode": "managed_helper",
                     "helper_host": "laptop", "state": "present"}
    checks = []
    for index, (enabled, flag, initial, expected) in enumerate([
        (True, False, [unrelated], [unrelated, fixed_jocasta]),
        (True, True, [unrelated], [unrelated, fixed_jocasta, target]),
        (False, True, [unrelated], [unrelated]),
        (True, True, [{"name": "holonet_catalog", "state": "absent"}],
         [fixed_jocasta, target | {"state": "absent"}]),
    ]):
        values = {"webmcp_interactive_enabled": enabled, FLAG: flag,
                  "mcp_registrations_remote_servers": initial}
        checks += [{**jocasta, "vars": values, "name": f"Baseline {index}"},
                   {**selection, "vars": values, "name": f"Select {index}"},
                   {"ansible.builtin.assert": {"that": ["mcp_registrations_effective_remote_servers == expected"]},
                    "vars": {"expected": expected}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr


def test_actual_credential_guard_refuses_unsafe_metadata_without_reading_a_secret(tmp_path):
    tasks = yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())
    inspect = next(t for t in tasks if t["name"].startswith("Inspect the separately delivered HoloNet"))
    assert inspect["ansible.builtin.stat"] == {
        "path": "{{ item }}", "follow": False, "get_checksum": False, "get_mime": False}
    assert inspect["loop"][-1].endswith("/holonet-interactive.app-password")
    guard = next(t for t in tasks if t["name"].startswith("Require private HoloNet"))
    rows = [{"item": f"/synthetic/{i}", "stat": {
        "exists": True, "islnk": False, "uid": 1001, "mode": "0700" if i == 3 else "0755",
        "isdir": i < 4, "isreg": i == 4, "nlink": 1, "size": 32}} for i in range(5)]
    rows[4]["stat"]["mode"] = "0600"
    cases = [(None, None, None)]
    cases += [(4, "mode", "0644"), (4, "nlink", 2), (4, "uid", 0), (4, "islnk", True),
              (4, "size", 15), (4, "size", 257), (3, "mode", "0755"), (3, "uid", 0),
              (1, "islnk", True), (4, "exists", False)]
    checks = []
    for index, (row, field, value) in enumerate(cases):
        data = copy.deepcopy(rows)
        if row is not None:
            data[row]["stat"][field] = value
        checks += [{**guard, "name": f"Guard {index}", "ignore_errors": True, "register": "observed",
                    "vars": {FLAG: True, "ansible_facts": {"user_uid": 1001},
                             "webmcp_interactive_holonet_credential": {"results": data}}},
                   {"ansible.builtin.assert": {"that": [
                       "observed.failed | default(false) == expected_failure"]},
                    "vars": {"expected_failure": row is not None}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr
