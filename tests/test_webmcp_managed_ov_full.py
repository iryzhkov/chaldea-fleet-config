"""The closed full interactive OV registration and its default-off selection.

Synthetic client configs and scratch homes only. Nothing here reads a real
credential, runs the helper, enrolls an account or qualifies official T3,
Codex or Claude.
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
HELPER = "/usr/local/libexec/webmcp-interactive-headers"
NARROW = HELPER + " ov laptop"
FULL_HOSTS = ("laptop", "omarchy-pc")
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
SECRET_BYTES = "FixtureOVFullAppPassword0123456789"


def full(**change):
    return dict(name="ov", transport="remote", url=OV_URL, auth_mode="managed_helper",
                helper_host="laptop", helper_profile="ov-full") | change


def test_closed_profiles_keep_ov_full_and_the_narrow_tuple_with_holonet_reader():
    assert set(module_code.MANAGED_SERVERS) == {"jocasta", "ov", "holonet_catalog"}
    assert module_code.MANAGED_SERVERS["ov"] == {"url": OV_URL, "providers": frozenset({"codex"}),
                                                 "commands": {"laptop": NARROW}}
    assert module_code.MANAGED_PROFILES == {"ov-full": {
        "name": "ov", "url": OV_URL, "providers": frozenset({"claude", "codex"}),
        "commands": {"laptop": HELPER + " ov-full laptop", "omarchy-pc": HELPER + " ov-full omarchy-pc"}}}


@pytest.mark.parametrize("host", FULL_HOSTS)
@pytest.mark.parametrize("provider,field", [("codex", "http_headers_helper"), ("claude", "headersHelper")])
def test_full_registration_roundtrip_preserves_jocasta_and_unrelated(tmp_path, host, provider, field):
    path = tmp_path / ("config.toml" if provider == "codex" else "claude.json")
    other = {"type": "http", "url": "https://other.example/mcp", "headers": {"Authorization": SECRET}}
    if provider == "codex":
        path.write_text(CODEX_CONFIG)
        kwargs = {"codex_config": str(path)}
    else:
        path.write_text(json.dumps({"private": SECRET, "mcpServers": {"other": other}}))
        kwargs = {"claude_config": str(path), "claude_command": [sys.executable, FAKE_CLAUDE, "--user-config", str(path)]}
    jocasta = dict(name="jocasta", transport="remote", url=URL, auth_mode="managed_helper", helper_host=host, **kwargs)
    assert call(provider, **jocasta)["changed"]
    params = full(helper_host=host, **kwargs)
    result = call(provider, **params)
    assert result["changed"] and SECRET not in json.dumps(result)
    doc = tomllib.loads(path.read_text()) if provider == "codex" else json.loads(path.read_text())
    servers = doc["mcp_servers" if provider == "codex" else "mcpServers"]
    assert servers["ov"] == {"url": OV_URL, field: HELPER + " ov-full " + host,
                             **({"type": "http"} if provider == "claude" else {})}
    assert servers["jocasta"][field] == module_code.HELPER + host
    if provider == "codex":
        # Every pre-existing table, stdio or remote, is untouched.
        original = tomllib.loads(CODEX_CONFIG)["mcp_servers"]
        assert {name: servers[name] for name in original} == original
        assert servers["other"]["http_headers"]["Authorization"] == SECRET
    else:
        assert doc["private"] == SECRET and servers["other"] == other
    assert not call(provider, **params)["changed"]
    assert not call(provider, **jocasta)["changed"]
    assert call(provider, **(params | {"state": "absent"}))["changed"]
    final = tomllib.loads(path.read_text()) if provider == "codex" else json.loads(path.read_text())
    final = final["mcp_servers" if provider == "codex" else "mcpServers"]
    assert "ov" not in final and "other" in final and final["jocasta"] == servers["jocasta"]


def test_full_replaces_the_narrow_laptop_codex_entry_in_place(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG)
    narrow = dict(name="ov", transport="remote", url=OV_URL, auth_mode="managed_helper",
                  helper_host="laptop", codex_config=str(path))
    assert call("codex", **narrow)["changed"]
    assert tomllib.loads(path.read_text())["mcp_servers"]["ov"]["http_headers_helper"] == NARROW
    assert call("codex", **full(codex_config=str(path)))["changed"]
    servers = tomllib.loads(path.read_text())["mcp_servers"]
    assert servers["ov"] == {"url": OV_URL, "http_headers_helper": HELPER + " ov-full laptop"}
    assert [name for name in servers if servers[name].get("url") == OV_URL] == ["ov"]
    # Rollback to the narrow tuple is the same in-place replacement.
    assert call("codex", **narrow)["changed"]
    assert tomllib.loads(path.read_text())["mcp_servers"]["ov"] == {"url": OV_URL, "http_headers_helper": NARROW}


@pytest.mark.parametrize("change", [
    {"helper_host": "agent-a"}, {"helper_host": "agent-b"}, {"helper_host": "controller"}, {"helper_host": None},
    {"helper_profile": "ov-wide"}, {"helper_profile": "OV-FULL"}, {"helper_profile": ""}, {"helper_profile": "ov"},
    {"helper_profile": "jocasta"}, {"name": "ov-memory"}, {"name": "jocasta"}, {"name": "ov-full"},
    {"url": URL}, {"url": OV_URL + "/"}, {"url": "https://ov.ryzhkov.dev/mcp"},
    {"extra": {"headers": {"Authorization": SECRET}}}, {"extra": {"http_headers_helper": HELPER + " ov-full laptop"}},
    {"extra": {"scopes": ["ov.read", "ov.write"]}}, {"auth_mode": "oauth"},
])
def test_full_profile_refuses_drift_before_native_write(tmp_path, change):
    path = tmp_path / "config.toml"
    with pytest.raises(Failed):
        call("codex", codex_config=str(path), **full(**change))
    assert not path.exists()


def test_full_profile_is_claude_and_codex_only_and_never_stdio(tmp_path):
    with pytest.raises(Failed):
        call("opencode", opencode_config=str(tmp_path / "opencode.json"), **full())
    assert not (tmp_path / "opencode.json").exists()
    with pytest.raises(Failed):
        call("codex", name="ov", command="/fixture", helper_profile="ov-full", codex_config=str(tmp_path / "c.toml"))
    with pytest.raises(Failed):
        call("codex", name="ov", transport="remote", url=OV_URL, helper_profile="ov-full",
             codex_config=str(tmp_path / "c.toml"))
    assert not (tmp_path / "c.toml").exists()
    # Only the fixed commands count as public; any suffix stays hidden.
    for host in FULL_HOSTS:
        command = HELPER + " ov-full " + host
        assert module_code.public_projection("claude", {"headersHelper": command})["headersHelper"] == command
        hidden = module_code.public_projection("codex", {"http_headers_helper": command + " --x"})
        assert isinstance(hidden["http_headers_helper"], module_code.Hidden)
    for key in SECRET_KEYS:
        with pytest.raises(Failed):
            call("codex", codex_config=str(tmp_path / "c.toml"), name="ov", transport="remote", url=OV_URL,
                 extra={key: HELPER + " ov-full laptop"})


def selection_tasks():
    tasks = yaml.safe_load((ROOT / "roles/mcp_registrations/tasks/main.yml").read_text())
    names = ("Select explicit", "Select the closed laptop OV", "Select the full interactive OV")
    return [next(t for t in tasks if t["name"].startswith(prefix)) for prefix in names]


@pytest.mark.parametrize("host", ["laptop", "omarchy-pc", "agent-a"])
def test_actual_ansible_selection_is_default_off_and_replaces_by_name(tmp_path, host):
    tasks = selection_tasks()
    unrelated = {"name": "unrelated", "url": "https://other.example/mcp", "providers": ["codex"]}
    jocasta = {"name": "jocasta", "url": URL, "providers": ["claude", "codex"], "auth_mode": "managed_helper",
               "helper_host": host, "state": "present"}
    managed = {"name": "ov", "url": OV_URL, "providers": ["claude", "codex"], "auth_mode": "managed_helper",
               "helper_host": host, "helper_profile": "ov-full", "state": "present"}
    cases = [
        # (managed Jocasta, full OV opt-in, remotes, expected)
        (True, None, [unrelated], [unrelated, jocasta]),
        (True, False, [unrelated], [unrelated, jocasta]),
        (True, True, [unrelated], [unrelated, jocasta, managed]),
        (True, True, [{"name": "ov", "state": "absent"}], [jocasta, {**managed, "state": "absent"}]),
        (False, True, [unrelated], [unrelated]),
    ]
    play_tasks = []
    for index, (enabled, full_enabled, remotes, expected) in enumerate(cases):
        variables = {"webmcp_interactive_enabled": enabled, "mcp_registrations_remote_servers": remotes}
        if full_enabled is not None:
            variables["webmcp_interactive_ov_full_enabled"] = full_enabled
        play_tasks += [{**task, "name": f"{task['name']} {index}", "vars": variables} for task in tasks]
        play_tasks.append({"name": f"Verify {index}", "vars": {"expected": expected},
                           "ansible.builtin.assert": {"that": ["mcp_registrations_effective_remote_servers == expected"]}})
    play = tmp_path / "selection.yml"
    play.write_text(yaml.safe_dump([{"hosts": host, "connection": "local", "gather_facts": False, "tasks": play_tasks}]))
    result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)], env=ENV, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    if host == "agent-a":
        # Selection names the host; the module refuses an unapproved one.
        with pytest.raises(Failed):
            call("codex", codex_config=str(tmp_path / "config.toml"), **full(helper_host=host))


def role_tasks():
    return yaml.safe_load((ROOT / "roles/webmcp_interactive/tasks/main.yml").read_text())


@pytest.mark.parametrize("host,narrow,ok", [("laptop", False, True), ("omarchy-pc", False, True),
                                            ("agent-a", False, False), ("agent-b", False, False),
                                            ("laptop", True, False)])
def test_role_preflight_binds_hosts_and_excludes_the_narrow_selection(tmp_path, host, narrow, ok):
    play = tmp_path / "preflight.yml"
    play.write_text(yaml.safe_dump([{"hosts": host, "connection": "local", "gather_facts": False, "vars": {
        "webmcp_interactive_enabled": True, "webmcp_interactive_laptop_qualified": True,
        "webmcp_interactive_ov_full_enabled": True, "webmcp_interactive_ov_enabled": narrow,
        "webmcp_interactive_helper_source": "/fixture/helper", "webmcp_interactive_helper_sha256": "0" * 64,
        "webmcp_interactive_credential_source": "/fixture/enrollment",
        "fleet_home": str(tmp_path), "ansible_facts": {"user_dir": str(tmp_path)}},
        "tasks": role_tasks()[:1]}]))
    result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)], env=ENV, capture_output=True, text=True)
    assert (result.returncode == 0) is ok, result.stdout + result.stderr


def custody_play(tmp_path, home, enabled=True):
    check = [t for t in role_tasks() if "full interactive OV app password" in t["name"]
             or "full OV app-password custody" in t["name"]]
    assert [t["name"] for t in check] == [
        "Inspect the separately delivered full interactive OV app password without reading it",
        "Require private full OV app-password custody before registering its helper"]
    assert check[0]["ansible.builtin.stat"]["get_checksum"] is False and check[0]["ansible.builtin.stat"]["follow"] is False
    play = tmp_path / "custody.yml"
    play.write_text(yaml.safe_dump([{"hosts": "omarchy-pc", "connection": "local", "gather_facts": False, "vars": {
        "fleet_home": str(home), "webmcp_interactive_ov_full_enabled": enabled,
        "ansible_facts": {"user_uid": os.getuid()}}, "tasks": check}]))
    result = subprocess.run(["ansible-playbook", "-i", "omarchy-pc,", str(play)], env=ENV, capture_output=True, text=True)
    assert SECRET_BYTES not in result.stdout + result.stderr
    return result


def private_home(tmp_path):
    home = tmp_path / "home"
    private = home / ".config/chaldea/authentik"
    private.mkdir(parents=True)
    for parent in (home, home / ".config", home / ".config/chaldea"):
        parent.chmod(0o755)
    private.chmod(0o700)
    target = private / "ov-full-interactive.app-password"
    target.write_text(SECRET_BYTES)
    target.chmod(0o600)
    return home, target


@pytest.mark.parametrize("unsafe", [None, "missing", "narrow-only", "group-readable", "shared-directory", "symlink",
                                    "hard-link", "oversized", "short"])
def test_full_credential_custody_is_checked_without_reading_it(tmp_path, unsafe):
    home, target = private_home(tmp_path)
    private = target.parent
    if unsafe == "missing":
        target.unlink()
    elif unsafe == "narrow-only":
        # The narrow interactive file never stands in for the full one.
        target.rename(private / "ov-interactive-codex.app-password")
    elif unsafe == "group-readable":
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
    elif unsafe == "short":
        target.write_text("x" * 15)
    result = custody_play(tmp_path, home)
    if unsafe is None:
        assert result.returncode == 0, result.stdout + result.stderr
        assert target.read_text() == SECRET_BYTES and target.stat().st_mode & 0o777 == 0o600
    else:
        assert result.returncode != 0
        assert "Require private full OV app-password custody before registering its helper" in result.stdout
    assert custody_play(tmp_path, tmp_path / "absent", enabled=False).returncode == 0


def test_capability_defaults_off_and_only_selected_interactive_hosts_opt_in():
    defaults = yaml.safe_load((ROOT / "roles/webmcp_interactive/defaults/main.yml").read_text())
    assert defaults["webmcp_interactive_ov_full_enabled"] is False
    owners = {
        ROOT / "inventory/host_vars/laptop/jocasta-interactive.yml",
        ROOT / "inventory/host_vars/omarchy-pc/ov-memory.yml",
    }
    selected = set()
    for path in (ROOT / "inventory").rglob("*"):
        if path.is_file() and path.suffix in (".yml", ".yaml"):
            values = yaml.safe_load(path.read_text())
            if isinstance(values, dict) and "webmcp_interactive_ov_full_enabled" in values:
                assert path in owners and values["webmcp_interactive_ov_full_enabled"] is True
                assert not values.get("webmcp_interactive_ov_enabled", False)
                selected.add(path)
    assert selected == owners
    # Default stdio remains available; only the two migrated hosts select absence.
    from jinja2 import Environment
    env = Environment()
    env.filters["bool"] = bool
    servers = yaml.safe_load((ROOT / "roles/mcp_registrations/defaults/main.yml").read_text())["mcp_registrations_servers"]
    selected = [s for s in servers if s["name"] == "ov-memory"][0]
    assert yaml.safe_load(env.from_string(selected["enabled"]).render()) is True
    assert yaml.safe_load(env.from_string(selected["enabled"]).render(mcp_registrations_ov_memory_enabled=False)) is False
    disabled = set()
    for path in (ROOT / "inventory").rglob("*.yml"):
        values = yaml.safe_load(path.read_text())
        if isinstance(values, dict) and "mcp_registrations_ov_memory_enabled" in values:
            assert values["mcp_registrations_ov_memory_enabled"] is False
            disabled.add(path.parent.name)
    assert disabled == {"laptop", "omarchy-pc"}


def test_inert_activation_example_is_exact_and_uses_accepted_host_artifacts():
    example = yaml.safe_load((ROOT / "docs/examples/ov-full-interactive.yml").read_text())
    assert set(example["hosts"]) == set(FULL_HOSTS)
    for host, item in example["hosts"].items():
        assert item["selection"] == {"webmcp_interactive_ov_full_enabled": True}
        assert item["entries"] == {
            "codex": {"name": "ov", "url": OV_URL, "http_headers_helper": HELPER + " ov-full " + host},
            "claude": {"name": "ov", "type": "http", "url": OV_URL, "headersHelper": HELPER + " ov-full " + host}}
        assert item["credential"] == {
            "path": "/home/igor/.config/chaldea/authentik/ov-full-interactive.app-password",
            "username": "chaldea-" + host + "-ov-full-interactive"}
    assert example["hosts"]["laptop"]["binding"] == {"node": "omarchy-macbook-air-igor", "uid": 1001}
    assert example["hosts"]["omarchy-pc"]["binding"] == {"node": "omarchy-pc", "uid": 1000}
    # Artifact pins are host-specific; the reference is never loaded as inventory.
    assert example["helper_pin"] == {
        "status": "accepted-source builds",
        "sha256_by_host": {
            "laptop": "dafb0ec33a28e969b8b344c2815e47cfdc1894f4e8a5ec7db3f992dbed6d56bc",
            "omarchy-pc": "acefaa482584d26ce8cd471edc10577ee925c0a6c36c9e97e000ba3ce8ffb7be",
        },
    }
    text = (ROOT / "docs/examples/ov-full-interactive.yml").read_text()
    assert "previous_helper_sha256" not in text
