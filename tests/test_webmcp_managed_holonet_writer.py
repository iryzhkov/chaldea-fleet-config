"""Separate native writer, exact public cohort and preserved ordinary readers."""
import copy
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, FakeModule, call, module_code
from test_webmcp_managed_holonet import _ansible, reader
from test_webmcp_managed_ov import selection_tasks

ROOT = Path(__file__).resolve().parents[1]
URL = "https://media.mcp.ryzhkov.dev/mcp"
HELPER = "/usr/local/libexec/webmcp-interactive-headers holonet-writer laptop"
FLAG = "webmcp_interactive_holonet_writer_enabled"
TARGETS = ["b" * 32, "c" * 32]


def writer(**changes):
    return {"name": "holonet_recommendations", "transport": "remote", "url": URL,
            "auth_mode": "managed_helper", "helper_host": "laptop"} | changes


def writer_tasks():
    return yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/holonet-writer.yml").read_text())


def test_separate_writer_codex_registration_repeat_and_inverse_preserve_reader(tmp_path):
    assert module_code.MANAGED_SERVERS["holonet_recommendations"] == {
        "url": URL, "providers": frozenset({"claude", "codex"}), "commands": {"laptop": HELPER}}
    path = tmp_path / "config.toml"
    call("codex", codex_config=str(path), **reader())
    before = path.read_bytes()
    result = call("codex", codex_config=str(path), **writer())
    assert result["changed"]
    assert not call("codex", codex_config=str(path), **writer())["changed"]
    assert call("codex", codex_config=str(path), **writer(state="absent"))["changed"]
    assert tomllib.loads(path.read_text()) == tomllib.loads(before.decode())


def test_writer_claude_roundtrip_preserves_reader_and_private_neighbors(tmp_path):
    path = tmp_path / "claude.json"
    before = {"private": "synthetic-retain", "mcpServers": {
        "holonet_catalog": {"type": "http", "url": URL,
                            "headersHelper": "/usr/local/libexec/webmcp-interactive-headers holonet laptop"},
        "other": {"type": "http", "url": "https://other.invalid/mcp"}}}
    path.write_text(json.dumps(before))
    params = {"claude_config": str(path),
              "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    assert call("claude", check_mode=True, **params, **writer())["changed"]
    assert json.loads(path.read_text()) == before
    assert call("claude", **params, **writer())["changed"]
    expected = copy.deepcopy(before)
    expected["mcpServers"]["holonet_recommendations"] = {"type": "http", "url": URL, "headersHelper": HELPER}
    assert json.loads(path.read_text()) == expected
    assert not call("claude", **params, **writer())["changed"]
    assert call("claude", **params, **writer(state="absent"))["changed"]
    assert json.loads(path.read_text()) == before


@pytest.mark.parametrize("provider", ["claude", "codex", "opencode"])
@pytest.mark.parametrize("change", [
    {"helper_host": "agent-a"}, {"helper_host": "omarchy-pc"},
    {"url": URL + "/"}, {"extra": {"headers": {"Authorization": "never install"}}},
    {"helper_profile": "ov-full"},
])
def test_writer_closed_tuple_rejects_drift(provider, change):
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), provider, {"extra": {}, **writer(**change)})
    with pytest.raises(Failed):
        module_code.remote_definition(FakeModule(False), "opencode", {"extra": {}, **writer()})


def test_actual_writer_selection_is_default_off_and_preserves_reader(tmp_path):
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults[FLAG] is False
    assert defaults["webmcp_interactive_holonet_writer_targets"] == []
    assert all(FLAG not in p.read_text(errors="replace") for p in (ROOT / "inventory").rglob("*.yml"))
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    selection = next(t for t in tasks if t["name"].startswith("Select the closed laptop HoloNet recommendation writer"))
    base, _ = selection_tasks()
    existing = {"name": "holonet_catalog", "url": URL, "providers": ["claude", "codex"],
                "auth_mode": "managed_helper", "helper_host": "laptop", "state": "present"}
    baseline_jocasta = {"name": "jocasta", "url": "https://jocasta.mcp.ryzhkov.dev/mcp",
                        "providers": ["claude", "codex"], "auth_mode": "managed_helper",
                        "helper_host": "laptop", "state": "present"}
    target = {"name": "holonet_recommendations", "url": URL, "providers": ["claude", "codex"],
              "auth_mode": "managed_helper", "helper_host": "laptop", "state": "present"}
    checks = []
    for index, (enabled, flag, desired, expected) in enumerate([
        (True, False, [existing], [existing, baseline_jocasta]),
        (True, True, [existing], [existing, baseline_jocasta, target]),
        (False, True, [existing], [existing]),
        (True, True, [existing, {"name": target["name"], "state": "absent"}],
         [existing, baseline_jocasta, target | {"state": "absent"}]),
    ]):
        values = {"webmcp_interactive_enabled": enabled, FLAG: flag,
                  "mcp_registrations_remote_servers": desired}
        checks += [{**base, "vars": values, "name": f"Baseline {index}"},
                   {**selection, "vars": values, "name": f"Writer {index}"},
                   {"ansible.builtin.assert": {"that": ["mcp_registrations_effective_remote_servers == expected"]},
                    "vars": {"expected": expected}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr


def test_actual_writer_cohort_guard_and_secret_metadata_are_closed(tmp_path):
    tasks = writer_tasks()
    validate = tasks[0]
    inspect = next(t for t in tasks if t["name"].startswith("Inspect the separately delivered"))
    assert inspect["ansible.builtin.stat"] == {
        "path": "{{ item }}", "follow": False, "get_checksum": False, "get_mime": False}
    assert inspect["loop"][-1].endswith("/holonet-recommendations.app-password")
    checks = []
    for index, cohort in enumerate([TARGETS, [], "*", {"b" * 32: True}, ["*"],
                                    ["B" * 32], [TARGETS[0]] * 2, [str(i).zfill(32) for i in range(17)]]):
        checks += [{**validate, "name": f"Cohort {index}", "ignore_errors": True, "register": "observed",
                    "vars": {"ansible_facts": {"user_uid": 1001},
                             "webmcp_interactive_holonet_writer_targets": cohort,
                             "webmcp_interactive_holonet_writer_previous_policy_sha256": ""}},
                   {"ansible.builtin.assert": {"that": ["observed.failed | default(false) == expected"]},
                    "vars": {"expected": index != 0}}]
    guard = next(t for t in tasks if t["name"].startswith("Require private HoloNet writer"))
    rows = [{"item": f"/synthetic/{i}", "stat": {
        "exists": True, "islnk": False, "uid": 1001, "mode": "0700" if i == 3 else "0755",
        "isdir": i < 4, "isreg": i == 4, "nlink": 1, "size": 32}} for i in range(5)]
    rows[4]["stat"]["mode"] = "0600"
    for index, change in enumerate([None, (4, "uid", 0), (4, "nlink", 2), (4, "mode", "0644"),
                                     (4, "islnk", True), (3, "mode", "0755")]):
        changed = copy.deepcopy(rows)
        if change:
            row, key, value = change
            changed[row]["stat"][key] = value
        checks += [{**guard, "name": f"Credential {index}", "ignore_errors": True, "register": "observed",
                    "vars": {"ansible_facts": {"user_uid": 1001},
                             "webmcp_interactive_holonet_writer_credential": {"results": changed}}},
                   {"ansible.builtin.assert": {"that": ["observed.failed | default(false) == expected"]},
                    "vars": {"expected": change is not None}}]
    result = _ansible(tmp_path, checks)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(os.geteuid() != 0, reason="exact root policy custody uses the Chaldea namespace")
def test_actual_public_policy_check_apply_repeat_and_foreign_digest_refusal(tmp_path):
    etc = tmp_path / "etc"
    etc.mkdir(mode=0o755)
    etc.chmod(0o755)
    desired = tmp_path / "etc/webmcp-interactive/holonet-recommendations.json"
    selected = []
    for task in writer_tasks():
        if task["name"].startswith(("Inspect the separately delivered", "Require private HoloNet writer")):
            continue
        task = copy.deepcopy(task)
        task.pop("become", None)  # This isolated job already has namespace UID0.
        # Redirect only the fixed public paths, never controller credentials.
        task = yaml.safe_load(yaml.safe_dump(task).replace("/etc/webmcp-interactive", str(etc / "webmcp-interactive"))
                              .replace("- /etc\n", "- " + str(etc) + "\n"))
        for args in task.values():
            if isinstance(args, dict):
                for field in ("owner", "group"):
                    if args.get(field) == "root":
                        args[field] = "0"
        selected.append(task)
    values = {"ansible_facts": {"user_uid": 1001},
              "webmcp_interactive_holonet_writer_targets": list(reversed(TARGETS)),
              "webmcp_interactive_holonet_writer_previous_policy_sha256": ""}
    def run(check=False):
        tasks = [{**task, "vars": values, **({"check_mode": True} if check else {})} for task in selected]
        return _ansible(tmp_path, tasks)
    planned = run(check=True)
    assert planned.returncode == 0, planned.stdout + planned.stderr
    assert not desired.exists()
    applied = run()
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert json.loads(desired.read_text()) == {
        "version": 1, "owner": "chaldea-fleet-config holonet recommendations", "target_users": TARGETS}
    assert desired.stat().st_mode & 0o777 == 0o644
    assert desired.stat().st_uid == 0
    repeated = run()
    assert repeated.returncode == 0 and "changed=0" in repeated.stdout, repeated.stdout + repeated.stderr
    desired.write_text('{"foreign":"retain"}')
    original = desired.read_bytes()
    refused = run()
    assert refused.returncode != 0
    assert desired.read_bytes() == original
