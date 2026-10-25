"""The closed laptop OV Codex helper registration and its default-off selection.

Synthetic client configs and scratch homes only. Nothing here reads a real
credential, runs the helper or qualifies official T3/Codex.
"""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, call, module_code
from test_mcp_remote_registration import CODEX_CONFIG, SECRET, SECRET_KEYS, URL

ROOT = Path(__file__).resolve().parents[1]
OV_URL = "https://ov.mcp.ryzhkov.dev/mcp"
OV_HELPER = "/usr/local/libexec/webmcp-interactive-headers ov laptop"
CREDENTIAL = ".config/chaldea/authentik/ov-interactive-codex.app-password"
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def ov(**change):
    return dict(name="ov", transport="remote", url=OV_URL, auth_mode="managed_helper", helper_host="laptop") | change


def test_closed_tuple_set_is_exactly_jocasta_and_laptop_ov():
    servers = module_code.MANAGED_SERVERS
    assert set(servers) == {"jocasta", "ov"}
    assert servers["ov"] == {"url": OV_URL, "providers": frozenset({"codex"}), "commands": {"laptop": OV_HELPER}}
    assert servers["jocasta"]["url"] == URL and servers["jocasta"]["providers"] == {"claude", "codex"}
    assert servers["jocasta"]["commands"] == {h: module_code.HELPER + h for h in ("laptop", "agent-a", "agent-b", "omarchy-pc")}


def test_ov_codex_registration_roundtrip_preserves_jocasta_and_unrelated(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG)
    jocasta = dict(name="jocasta", transport="remote", url=URL, auth_mode="managed_helper", helper_host="laptop",
                   codex_config=str(path))
    assert call("codex", **jocasta)["changed"]
    result = call("codex", codex_config=str(path), **ov())
    assert result["changed"] and SECRET not in json.dumps(result)
    servers = tomllib.loads(path.read_text())["mcp_servers"]
    assert servers["ov"] == {"url": OV_URL, "http_headers_helper": OV_HELPER}
    assert servers["jocasta"] == {"url": URL, "http_headers_helper": module_code.HELPER + "laptop"}
    assert servers["other"]["http_headers"]["Authorization"] == SECRET
    assert not call("codex", codex_config=str(path), **ov())["changed"]
    assert not call("codex", **jocasta)["changed"]
    assert call("codex", codex_config=str(path), **ov(state="absent"))["changed"]
    final = tomllib.loads(path.read_text())["mcp_servers"]
    assert "ov" not in final and "other" in final
    assert final["jocasta"] == servers["jocasta"]


@pytest.mark.parametrize("change", [
    {"helper_host": "agent-a"}, {"helper_host": "agent-b"}, {"helper_host": "omarchy-pc"}, {"helper_host": "homelab"},
    {"helper_host": None}, {"url": URL}, {"url": "https://ov.mcp.ryzhkov.dev/mcp/"}, {"url": "https://ov.ryzhkov.dev/mcp"},
    {"name": "ov-memory"}, {"name": "ov_tooling"}, {"name": "OV"},
    {"extra": {"headers": {"Authorization": SECRET}}}, {"extra": {"http_headers_helper": SECRET}},
    {"extra": {"http_headers_helper": OV_HELPER}}, {"extra": {"oauth": {"client_id": "ov-http-a63e197f-machine"}}},
    {"extra": {"scopes": ["ov.read"]}},
])
def test_ov_managed_mode_refuses_drift_before_native_write(tmp_path, change):
    path = tmp_path / "config.toml"
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), **ov(**change))
    assert not path.exists()


def test_jocasta_url_and_helper_cannot_be_crossed_with_ov(tmp_path):
    path = tmp_path / "config.toml"
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), **ov(name="jocasta"))
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), name="jocasta", transport="remote", url=OV_URL,
             auth_mode="managed_helper", helper_host="laptop")
    assert not path.exists()


def test_ov_is_codex_only(tmp_path):
    claude_config = tmp_path / "claude.json"
    claude_config.write_text(json.dumps({"mcpServers": {}}))
    with pytest.raises(Failed):
        call("claude", claude_config=str(claude_config),
             claude_command=[sys.executable, FAKE_CLAUDE, "--user-config", str(claude_config)], **ov())
    assert json.loads(claude_config.read_text()) == {"mcpServers": {}}
    with pytest.raises(Failed):
        call("opencode", opencode_config=str(tmp_path / "opencode.json"), **ov())
    assert not (tmp_path / "opencode.json").exists()
    with pytest.raises(Failed):
        call("codex", name="ov", command="/fixture", auth_mode="managed_helper", helper_host="laptop")


def test_oauth_mode_still_refuses_helpers_and_headers_for_ov(tmp_path):
    path = tmp_path / "config.toml"
    for key in SECRET_KEYS:
        for value in (SECRET, OV_HELPER):
            with pytest.raises(Failed):
                call("codex", codex_config=str(path), name="ov", transport="remote", url=OV_URL, extra={key: value})
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), name="ov", transport="remote", url=OV_URL, helper_host="laptop")
    assert not path.exists()
    # An unreviewed helper command never counts as public; the fixed ones do.
    projected = module_code.public_projection("codex", {"url": OV_URL, "http_headers_helper": OV_HELPER + " --x"})
    assert isinstance(projected["http_headers_helper"], module_code.Hidden)
    assert module_code.public_projection("codex", {"http_headers_helper": OV_HELPER})["http_headers_helper"] == OV_HELPER


def selection_tasks():
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    jocasta = next(t for t in tasks if t["name"].startswith("Select explicit"))
    ov_task = next(t for t in tasks if t["name"].startswith("Select the closed laptop OV"))
    return jocasta, ov_task


def test_actual_ansible_selection_is_default_off_and_laptop_bound(tmp_path):
    jocasta, ov_task = selection_tasks()
    unrelated = {"name": "unrelated", "url": "https://other.example/mcp", "providers": ["codex"]}
    managed_jocasta = {"name": "jocasta", "url": URL, "providers": ["claude", "codex"],
                       "auth_mode": "managed_helper", "helper_host": "laptop", "state": "present"}
    managed_ov = {"name": "ov", "url": OV_URL, "providers": ["codex"], "auth_mode": "managed_helper",
                  "helper_host": "laptop", "state": "present"}
    cases = [
        # (jocasta managed, OV opt-in, remotes, expected)
        (True, None, [unrelated], [unrelated, managed_jocasta]),
        (True, False, [unrelated], [unrelated, managed_jocasta]),
        (True, True, [unrelated], [unrelated, managed_jocasta, managed_ov]),
        (True, True, [{"name": "ov", "state": "absent"}], [managed_jocasta, {**managed_ov, "state": "absent"}]),
        (False, True, [unrelated], [unrelated]),
        (False, None, [{"name": "ov", "state": "absent"}], [{"name": "ov", "state": "absent"}]),
    ]
    play_tasks = []
    for index, (enabled, ov_enabled, remotes, expected) in enumerate(cases):
        variables = {"webmcp_interactive_enabled": enabled, "mcp_registrations_remote_servers": remotes}
        if ov_enabled is not None:
            variables["webmcp_interactive_ov_enabled"] = ov_enabled
        play_tasks += [
            {**jocasta, "name": f"Select Jocasta {index}", "vars": variables},
            {**ov_task, "name": f"Select OV {index}", "vars": variables},
            {"name": f"Verify {index}", "vars": {"expected": expected},
             "ansible.builtin.assert": {"that": ["mcp_registrations_effective_remote_servers == expected"]}},
        ]
    play = tmp_path / "selection.yml"
    play.write_text(yaml.safe_dump([{"hosts": "laptop", "connection": "local", "gather_facts": False,
                                     "tasks": play_tasks}]))
    result = subprocess.run(["ansible-playbook", "-i", "laptop,", str(play)], env=ENV, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    # On another host the entry names that host, which the module then refuses.
    other = tmp_path / "other.yml"
    other.write_text(yaml.safe_dump([{"hosts": "agent-a", "connection": "local", "gather_facts": False, "tasks": [
        {**jocasta, "vars": {"webmcp_interactive_enabled": True, "mcp_registrations_remote_servers": []}},
        {**ov_task, "vars": {"webmcp_interactive_enabled": True, "webmcp_interactive_ov_enabled": True,
                             "mcp_registrations_remote_servers": []}},
        {"ansible.builtin.assert": {"that": [
            "mcp_registrations_effective_remote_servers | selectattr('name', 'equalto', 'ov') "
            "| map(attribute='helper_host') | list == ['agent-a']"]}}]}]))
    result = subprocess.run(["ansible-playbook", "-i", "agent-a,", str(other)], env=ENV, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(Failed):
        call("codex", codex_config=str(tmp_path / "config.toml"), **ov(helper_host="agent-a"))


def test_capability_is_off_in_defaults_and_every_inventory_file():
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults["webmcp_interactive_ov_enabled"] is False
    for path in (ROOT / "inventory").rglob("*"):
        if path.is_file():
            text = path.read_text(errors="replace")
            assert "webmcp_interactive_ov_enabled" not in text, path
            assert "ov-interactive-codex" not in text, path
    laptop = yaml.safe_load((ROOT / "inventory/host_vars/laptop/jocasta-interactive.yml").read_text())
    assert [s["name"] for s in laptop["mcp_registrations_remote_servers"]] == ["jocasta"]
    # The protected limited OV preset keeps its own separate credential path.
    limited = yaml.safe_load((ROOT / "docs/examples/laptop-ov-tooling-codex.yml").read_text())
    assert limited["enrollments"]["ov-tooling-codex"]["secretFile"].endswith("/ov-tooling-codex.app-password")


def test_inert_activation_example_is_exact_and_invents_no_hash():
    example = yaml.safe_load((ROOT / "docs/examples/laptop-ov-interactive-codex.yml").read_text())
    assert example["selection"]["webmcp_interactive_ov_enabled"] is True
    assert example["selection"]["webmcp_interactive_helper_source"] == "/usr/local/libexec/webmcp-interactive-headers"
    assert example["codex_entry"] == {"name": "ov", "url": OV_URL, "http_headers_helper": OV_HELPER}
    assert example["credential"]["path"] == "/home/igor/" + CREDENTIAL
    assert example["credential"]["username"] == "chaldea-laptop-ov-interactive-codex"
    assert example["helper_pin"]["sha256"] == "FROM_REVIEWED_BUILD_RECEIPT"
    pins = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())["webmcp_interactive_helper_checksums"]
    assert example["helper_pin"]["previous_sha256"] == pins["aarch64"]
    assert example["helper_pin"]["architecture"] == "aarch64"


def role_tasks():
    return yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())


@pytest.mark.parametrize("host,ok", [("laptop", True), ("agent-a", False), ("omarchy-pc", False)])
def test_role_refuses_ov_outside_laptop_before_staging(tmp_path, host, ok):
    play = tmp_path / "preflight.yml"
    play.write_text(yaml.safe_dump([{"hosts": host, "connection": "local", "gather_facts": False, "vars": {
        "webmcp_interactive_enabled": True, "webmcp_interactive_laptop_qualified": True,
        "webmcp_interactive_ov_enabled": True, "webmcp_interactive_helper_source": "/fixture/helper",
        "webmcp_interactive_helper_sha256": "0" * 64, "webmcp_interactive_credential_source": "/fixture/enrollment",
        "fleet_home": str(tmp_path), "ansible_facts": {"user_dir": str(tmp_path)}},
        "tasks": role_tasks()[:1]}]))
    result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)], env=ENV, capture_output=True, text=True)
    assert (result.returncode == 0) is ok, result.stdout + result.stderr


SECRET_BYTES = "FixtureOVAppPassword0123456789"


def custody_play(tmp_path, home, enabled=True):
    tasks = role_tasks()
    check = [t for t in tasks if "OV credential" in t["name"]]
    assert [t["name"] for t in check] == [
        "Inspect the separately delivered laptop OV credential without reading it",
        "Require private OV credential custody before registering its helper"]
    play = tmp_path / "custody.yml"
    play.write_text(yaml.safe_dump([{"hosts": "laptop", "connection": "local", "gather_facts": False, "vars": {
        "fleet_home": str(home), "webmcp_interactive_ov_enabled": enabled,
        "ansible_facts": {"user_uid": os.getuid()}}, "tasks": check}]))
    result = subprocess.run(["ansible-playbook", "-i", "laptop,", str(play)], env=ENV, capture_output=True, text=True)
    assert SECRET_BYTES not in result.stdout + result.stderr
    return result


def private_home(tmp_path, content: str | None = SECRET_BYTES, mode=0o600, directory=0o700):
    home = tmp_path / "home"
    private = home / ".config/chaldea/authentik"
    private.mkdir(parents=True)
    for parent in (home, home / ".config", home / ".config/chaldea"):
        parent.chmod(0o755)
    target = private / "ov-interactive-codex.app-password"
    if content is not None:
        target.write_text(content)
        target.chmod(mode)
    private.chmod(directory)
    return home, target


def test_custody_check_accepts_infra_delivery_without_reading_it(tmp_path):
    inspect = next(t for t in role_tasks() if t["name"].startswith("Inspect the separately delivered laptop OV"))
    assert inspect["ansible.builtin.stat"]["get_checksum"] is False
    assert inspect["ansible.builtin.stat"]["follow"] is False
    home, target = private_home(tmp_path)
    result = custody_play(tmp_path, home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text() == SECRET_BYTES and target.stat().st_mode & 0o777 == 0o600
    assert custody_play(tmp_path, tmp_path / "absent", enabled=False).returncode == 0


@pytest.mark.parametrize("unsafe", ["missing", "group-readable", "shared-directory", "symlink", "hard-link",
                                    "oversized", "empty", "shared-ancestor", "directory"])
def test_custody_check_refuses_unsafe_credential_before_registration(tmp_path, unsafe):
    home, target = private_home(tmp_path, content=None if unsafe == "missing" else SECRET_BYTES)
    private = target.parent
    private.chmod(0o700)
    if unsafe == "group-readable":
        target.chmod(0o640)
    elif unsafe == "shared-directory":
        private.chmod(0o750)
    elif unsafe == "symlink":
        real = tmp_path / "elsewhere"
        real.write_text(SECRET_BYTES)
        real.chmod(0o600)
        target.unlink()
        target.symlink_to(real)
    elif unsafe == "hard-link":
        os.link(target, private / "copy")
    elif unsafe == "oversized":
        target.write_text("x" * 257)
    elif unsafe == "empty":
        target.write_text("")
    elif unsafe == "shared-ancestor":
        (home / ".config/chaldea").chmod(0o777)
    elif unsafe == "directory":
        target.unlink()
        target.mkdir(mode=0o700)
    result = custody_play(tmp_path, home)
    assert result.returncode != 0
    assert "Require private OV credential custody before registering its helper" in result.stdout
