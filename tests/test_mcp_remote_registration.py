"""Remote (native OAuth) registrations: module shapes, drift, secrecy and the laptop role.

Everything runs against synthetic scratch configs and tests/fake-claude; no
real client, credential store or network is touched.
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from test_mcp_registration import FAKE_CLAUDE, Failed, call

ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE = ROOT / "inventory/host_vars/laptop/jocasta-interactive.yml"
URL = "https://jocasta.mcp.ryzhkov.dev/mcp"
CLIENT = "jocasta-laptop-interactive"
SCOPE = "jocasta.read jocasta.write offline_access"
SECRET = "SECRET-sentinel-4f1c"
EXTRA = {
    "claude": {"oauth": {"clientId": CLIENT, "callbackPort": 43182, "scopes": SCOPE}},
    "codex": {"scopes": SCOPE.split(), "oauth": {
        "client_id": CLIENT, "callback_port": 43181, "callback_url": "http://127.0.0.1:43181/callback/bbdouGp56E53"}},
    "opencode": {"oauth": {"clientId": CLIENT, "scope": SCOPE, "callbackPort": 43183,
                            "redirectUri": "http://127.0.0.1:43183/callback"}},
}
STDIO_KEYS = {"command", "args", "env", "environment", "cwd", "env_vars"}
SECRET_KEYS = {"headers", "headersHelper", "http_headers", "env_http_headers", "http_headers_helper",
               "bearer_token", "bearer_token_env_var", "clientSecret", "client_secret"}


def remote(provider, **params):
    return {"name": "jocasta", "transport": "remote", "url": URL, "extra": EXTRA[provider], **params}


def keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


@pytest.fixture(autouse=True)
def scratch_cwd(tmp_path, tmp_path_factory, monkeypatch):
    # conftest's scratch HOME; the fake CLI reads project/local scopes from the cwd.
    assert Path.home().is_relative_to(tmp_path_factory.getbasetemp())
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


# Inventory: the laptop-only binding and its exact public values.

def test_laptop_binding_is_the_adopted_public_design():
    values = yaml.safe_load(INTERACTIVE.read_text())
    assert values["mcp_registrations_jocasta_interactive_state"] == "present"
    [server] = values["mcp_registrations_remote_servers"]
    assert server == {"name": "jocasta", "state": "{{ mcp_registrations_jocasta_interactive_state }}",
                      "url": URL, "providers": ["claude", "codex"], **EXTRA}
    assert not set(keys(server)) & (SECRET_KEYS | STDIO_KEYS | {"oauth_resource", "token"})
    assert values["agent_config_fleet_tools_profile"]["tools"] == {"*": ["read", "write"]}


def test_codex_callback_is_its_own_suffix_for_the_canonical_url():
    suffix = base64.urlsafe_b64encode(hashlib.sha256(URL.encode()).digest()[:9]).decode().rstrip("=")
    assert EXTRA["codex"]["oauth"]["callback_url"] == f"http://127.0.0.1:43181/callback/{suffix}"


def inventory_vars(host):
    result = subprocess.run(["ansible-inventory", "-i", str(ROOT / "inventory/hosts.yml"), "--host", host],
                            text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_only_the_laptop_opts_in_and_the_role_default_is_off():
    defaults = yaml.safe_load((ROOT / "roles/mcp_registrations/defaults/main.yml").read_text())
    assert defaults["mcp_registrations_remote_servers"] == []
    assert defaults["mcp_registrations_providers"] == ["claude", "codex"]
    agent_defaults = yaml.safe_load((ROOT / "roles/agent_config/defaults/main.yml").read_text())
    assert agent_defaults["agent_config_fleet_tools_profile"]["mcp"] == ["ov-memory"]
    for host in ("agent-a", "agent-b", "omarchy-pc", "normandy", "homelab"):
        values = inventory_vars(host)
        assert "mcp_registrations_remote_servers" not in values, host
        assert "agent_config_fleet_tools_profile" not in values, host
    laptop = inventory_vars("laptop")
    assert [server["name"] for server in laptop["mcp_registrations_remote_servers"]] == ["jocasta"]
    # The protected tooling profiles stay isolated from the operator server.
    codex = laptop["chaldea_client_session_profiles"]["jocasta-tooling-codex"]
    assert "jocasta" in codex["disabled_servers"] and codex["home"] != "/home/igor"
    assert laptop["chaldea_client_session_profiles"]["jocasta-tooling-claude"]["server"] == "jocasta_tooling"


# Codex

CODEX_CONFIG = f"""\
# Personal settings stay as they are.
model = "gpt-6"

[model_providers.private]
experimental_bearer_token = "{SECRET}"

[mcp_servers.other]
url = "https://other.example/mcp"
http_headers = {{ Authorization = "{SECRET}" }}

[mcp_servers.huyang]
command = "/opt/huyang"
args = ["mcp"]

[projects."/home/user"]
trust_level = "trusted"
"""


def test_codex_writes_the_public_remote_table_and_then_converges(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG)
    before = tomllib.loads(CODEX_CONFIG)

    result = call("codex", codex_config=str(path), **remote("codex"))

    text = path.read_text()
    document = tomllib.loads(text)
    assert result["changed"]
    assert document["mcp_servers"]["jocasta"] == {"url": URL, **EXTRA["codex"]}
    assert not set(document["mcp_servers"]["jocasta"]) & (STDIO_KEYS | SECRET_KEYS)
    assert {key: value for key, value in document.items() if key != "mcp_servers"} == {
        key: value for key, value in before.items() if key != "mcp_servers"}
    assert document["mcp_servers"]["other"] == before["mcp_servers"]["other"]
    assert document["mcp_servers"]["huyang"] == before["mcp_servers"]["huyang"]
    assert "# Personal settings stay as they are.\n" in text
    assert SECRET not in json.dumps(result)
    assert not call("codex", codex_config=str(path), **remote("codex"))["changed"]
    assert path.read_text() == text


def test_codex_replaces_secret_bearing_drift_without_showing_it(tmp_path):
    path = tmp_path / "config.toml"
    stale = CODEX_CONFIG + f"""
[mcp_servers.jocasta]
url = "{URL}"
bearer_token = "{SECRET}"

[mcp_servers.jocasta.oauth]
client_id = "{CLIENT}"
client_secret = "{SECRET}"
callback_port = 43181

[mcp_servers.jocasta.http_headers]
Authorization = "{SECRET}"
"""
    path.write_text(stale)

    check = call("codex", check_mode=True, codex_config=str(path), **remote("codex"))
    assert check["changed"] and path.read_text() == stale
    result = call("codex", codex_config=str(path), **remote("codex"))

    shown = json.dumps([check, result])
    assert SECRET not in shown
    before = json.loads(result["diff"]["before"])
    assert before["bearer_token"] == "<redacted>" and before["oauth"]["client_secret"] == "<redacted>"
    assert before["http_headers"] == {"Authorization": "<redacted>"}
    document = tomllib.loads(path.read_text())
    assert document["mcp_servers"]["jocasta"] == {"url": URL, **EXTRA["codex"]}
    # The unrelated credential-bearing tables are preserved byte for byte.
    assert path.read_text().count(SECRET) == 2


def test_codex_public_oauth_drift_reconciles_and_absence_removes_nested_tables(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG + f'\n[mcp_servers.jocasta]\nurl = "{URL}"\nscopes = ["jocasta.read"]\n'
                    f'\n[mcp_servers.jocasta.oauth]\nclient_id = "{CLIENT}"\ncallback_port = 1234\n')

    result = call("codex", codex_config=str(path), **remote("codex"))

    assert result["changed"]
    after = json.loads(result["diff"]["after"])
    assert after["oauth"]["callback_port"] == "<redacted, changed>" and after["oauth"]["client_id"] == "<redacted>"
    assert after["scopes"] == SCOPE.split()
    assert tomllib.loads(path.read_text())["mcp_servers"]["jocasta"] == {"url": URL, **EXTRA["codex"]}
    assert call("codex", codex_config=str(path), name="jocasta", transport="remote", state="absent")["changed"]
    text = path.read_text()
    assert "jocasta" not in text and tomllib.loads(text)["mcp_servers"].keys() == {"other", "huyang"}
    assert not call("codex", codex_config=str(path), name="jocasta", transport="remote", state="absent")["changed"]


# OpenCode

def test_opencode_writes_a_remote_entry_preserving_other_settings(tmp_path):
    path = tmp_path / "opencode.json"
    original = {"model": "keep", "provider": {"private": {"options": {"apiKey": SECRET}}},
                "mcp": {"other": {"type": "remote", "url": "https://other.example", "headers": {"Authorization": SECRET}},
                        "jocasta": {"type": "local", "command": ["/old"], "environment": {"TOKEN": SECRET},
                                    "oauth": {"clientSecret": SECRET}}}}
    path.write_text(json.dumps(original))
    path.chmod(0o640)

    result = call("opencode", opencode_config=str(path), **remote("opencode"))

    document = json.loads(path.read_text())
    assert result["changed"] and SECRET not in json.dumps(result)
    assert document["mcp"]["jocasta"] == {"type": "remote", "url": URL, **EXTRA["opencode"], "enabled": True}
    assert document["mcp"]["other"] == original["mcp"]["other"]
    assert {key: document[key] for key in ("model", "provider")} == {key: original[key] for key in ("model", "provider")}
    assert path.stat().st_mode & 0o777 == 0o640
    before = path.read_bytes()
    assert not call("opencode", opencode_config=str(path), **remote("opencode"))["changed"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("layout", ["symlink", "jsonc"])
def test_opencode_remote_refuses_symlinks_and_jsonc_peers(tmp_path, layout):
    path = tmp_path / "opencode.json"
    if layout == "symlink":
        target = tmp_path / "elsewhere.json"
        target.write_text("{}")
        path.symlink_to(target)
    else:
        path.write_text("{}")
        (tmp_path / "opencode.jsonc").write_text("// owner\n{}")

    with pytest.raises(Failed, match="symlink or has a JSONC peer"):
        call("opencode", opencode_config=str(path), **remote("opencode"))
    assert (tmp_path / ("elsewhere.json" if layout == "symlink" else "opencode.json")).read_text() == "{}"


# Claude: user-scope only, through the CLI, compared by public projection.

def claude_config(tmp_path, servers, **extra):
    path = tmp_path / ".claude.json"
    path.write_text(json.dumps({"oauthAccount": {"accessToken": SECRET}, "primaryApiKey": SECRET,
                                "projects": {"/elsewhere": {"mcpServers": {"x": {"env": {"T": SECRET}}}}},
                                "mcpServers": servers, **extra}))
    return path


def claude(path, **params):
    return call("claude", claude_command=[FAKE_CLAUDE, "--user-config", str(path)], claude_config=str(path),
                **{**remote("claude"), **params})


def user_servers(path):
    return json.loads(path.read_text())["mcpServers"]


def test_claude_registers_through_the_cli_preserving_private_state(tmp_path):
    other = {"type": "http", "url": "https://other.example", "headers": {"Authorization": SECRET}}
    path = claude_config(tmp_path, {"other": other})
    private = {key: value for key, value in json.loads(path.read_text()).items() if key != "mcpServers"}

    result = claude(path)

    document = json.loads(path.read_text())
    assert result["changed"] and SECRET not in json.dumps(result)
    assert document["mcpServers"] == {"other": other, "jocasta": {"type": "http", "url": URL, **EXTRA["claude"]}}
    assert {key: value for key, value in document.items() if key != "mcpServers"} == private
    before = path.read_bytes()
    assert not claude(path)["changed"]
    assert path.read_bytes() == before  # No CLI mutation on the second run.


def test_claude_detects_oauth_drift_that_mcp_get_cannot_show(tmp_path):
    stale = {"type": "http", "url": URL, "oauth": {**EXTRA["claude"]["oauth"], "callbackPort": 1234}}
    path = claude_config(tmp_path, {"jocasta": stale})
    fake = [FAKE_CLAUDE, "--user-config", str(path), "mcp", "get", "jocasta"]
    shown_stale = subprocess.run(fake, capture_output=True, text=True).stdout

    result = claude(path)

    assert result["changed"]
    assert json.loads(result["diff"]["after"])["oauth"]["callbackPort"] == "<redacted, changed>"
    assert user_servers(path)["jocasta"] == {"type": "http", "url": URL, **EXTRA["claude"]}
    assert subprocess.run(fake, capture_output=True, text=True).stdout == shown_stale


@pytest.mark.parametrize("field", [{"headers": {"Authorization": SECRET}}, {"headersHelper": "/bin/" + SECRET},
                                   {"oauth": {"clientId": CLIENT, "clientSecret": SECRET}}, {"unknown": SECRET}])
def test_claude_secret_bearing_or_unknown_fields_are_drift_never_shown(tmp_path, field):
    stale = {"type": "http", "url": URL, **EXTRA["claude"], **field}
    path = claude_config(tmp_path, {"jocasta": stale})

    check = claude(path, check_mode=True)
    assert check["changed"] and user_servers(path)["jocasta"] == stale
    result = claude(path)

    assert SECRET not in json.dumps([check, result])
    assert "<redacted>" in result["diff"]["before"]
    assert user_servers(path)["jocasta"] == {"type": "http", "url": URL, **EXTRA["claude"]}
    assert not claude(path)["changed"]


def test_claude_absent_removes_only_the_user_registration(tmp_path):
    path = claude_config(tmp_path, {"jocasta": {"type": "http", "url": URL, "headers": {"A": SECRET}},
                                    "other": {"type": "stdio", "command": "/keep", "args": []}})

    result = claude(path, state="absent")

    assert result["changed"] and SECRET not in json.dumps(result)
    assert user_servers(path) == {"other": {"type": "stdio", "command": "/keep", "args": []}}
    assert not claude(path, state="absent")["changed"]


@pytest.mark.parametrize("scope", ["local", "project"])
def test_claude_refuses_a_shadowing_scope(tmp_path, scratch_cwd, scope):
    shadow = {"type": "http", "url": "https://shadow.example/mcp"}
    if scope == "local":
        path = claude_config(tmp_path, {}, projects={str(scratch_cwd): {"mcpServers": {"jocasta": shadow}}})
    else:
        path = claude_config(tmp_path, {})
        (scratch_cwd / ".mcp.json").write_text(json.dumps({"mcpServers": {"jocasta": shadow}}))
    before = path.read_bytes()

    with pytest.raises(Failed, match="hides the user registration"):
        claude(path)
    absent = claude(path, state="absent")
    assert not absent["changed"]
    assert path.read_bytes() == before


def test_claude_refuses_when_get_and_the_user_config_disagree(tmp_path):
    listed = tmp_path / "listed.json"
    listed.write_text(json.dumps({}))
    path = claude_config(tmp_path, {"jocasta": {"type": "http", "url": URL, **EXTRA["claude"]}})
    cli = [FAKE_CLAUDE, str(listed)]

    with pytest.raises(Failed, match="disagree"):
        call("claude", claude_command=cli, claude_config=str(path), **remote("claude"))
    listed.write_text(json.dumps({"jocasta": {"type": "http", "url": "https://other.example/mcp"}}))
    with pytest.raises(Failed, match="disagree"):
        call("claude", claude_command=cli, claude_config=str(path), **remote("claude"))
    with pytest.raises(Failed, match="disagree"):
        call("claude", claude_command=cli, claude_config=str(tmp_path / "missing.json"), **remote("claude"))


@pytest.mark.parametrize("layout", ["symlink", "jsonc", "servers-not-object", "entry-not-object", "directory"])
def test_claude_user_config_refusals_fail_closed_without_disclosure(tmp_path, layout):
    path = tmp_path / ".claude.json"
    real = claude_config(tmp_path, {}) if layout == "symlink" else None
    if layout == "symlink":
        real.rename(tmp_path / "real.json")
        path.symlink_to(tmp_path / "real.json")
    elif layout == "jsonc":
        path.write_text(f'// {SECRET}\n{{"mcpServers": {{}}}}')
    elif layout == "servers-not-object":
        path.write_text(json.dumps({"mcpServers": [SECRET]}))
    elif layout == "entry-not-object":
        path.write_text(json.dumps({"mcpServers": {"jocasta": SECRET}}))
    else:
        path.mkdir()
    listed = tmp_path / "listed.json"
    listed.write_text("{}")

    with pytest.raises(Failed) as failure:
        call("claude", claude_command=[FAKE_CLAUDE, str(listed)], claude_config=str(path), **remote("claude"))
    assert SECRET not in str(failure.value)
    assert listed.read_text() == "{}"


def test_claude_get_failure_is_not_echoed_for_a_remote_server(tmp_path):
    cli = tmp_path / "failing-claude"
    cli.write_text(f"#!/bin/sh\necho 'Headers: Authorization: {SECRET}'\nexit 2\n")
    cli.chmod(0o755)

    with pytest.raises(Failed) as failure:
        call("claude", claude_command=[str(cli)], claude_config=str(tmp_path / "none.json"), **remote("claude"))
    assert SECRET not in str(failure.value) and "status 2" in str(failure.value)


def test_parse_claude_get_ignores_nested_header_lines():
    from test_mcp_registration import module_code
    text = ("jocasta:\n  Scope: User config (available in all your projects)\n  Type: http\n"
            f"  URL: {URL}\n  Headers:\n    Scope: Local config\n    URL: https://spoof.example\n"
            "  OAuth: client_id configured\n")
    parsed = module_code.parse_claude_get(text)
    assert parsed["scope"].startswith("User") and parsed["url"] == URL and parsed["type"] == "http"


# Refusals of the desired definition.

@pytest.mark.parametrize("provider,extra", [
    ("claude", {"headers": {"Authorization": SECRET}}), ("claude", {"headersHelper": "/bin/helper"}),
    ("claude", {"oauth": {"clientId": CLIENT, "clientSecret": SECRET}}), ("claude", {"oauth": {}}),
    ("codex", {"bearer_token": SECRET}), ("codex", {"http_headers_helper": "/bin/helper"}),
    ("codex", {"oauth": {"client_id": CLIENT, "client_secret": SECRET}}), ("codex", {"oauth_resource": URL}),
    ("codex", {"oauth": {"client_id": CLIENT, "callback_port": "43181"}}),
    ("opencode", {"headers": {"Authorization": SECRET}}), ("opencode", {"oauth": {"clientSecret": SECRET}}),
    ("opencode", {"type": "local"}), ("opencode", {"enabled": False}),
])
def test_remote_refuses_non_public_options_before_writing(tmp_path, provider, extra):
    paths = {"codex_config": str(tmp_path / "config.toml"), "opencode_config": str(tmp_path / "opencode.json")}
    state = tmp_path / ".claude.json"
    state.write_text(json.dumps({"mcpServers": {}}))
    if provider == "claude":
        paths = {"claude_command": [FAKE_CLAUDE, "--user-config", str(state)], "claude_config": str(state)}

    with pytest.raises(Failed) as failure:
        call(provider, **paths, **{**remote(provider), "extra": extra})
    assert SECRET not in str(failure.value)
    assert not (tmp_path / "config.toml").exists() and not (tmp_path / "opencode.json").exists()
    assert json.loads(state.read_text()) == {"mcpServers": {}}


@pytest.mark.parametrize("params", [
    {"url": "http://jocasta.example/mcp"}, {"url": "https://user:pw@jocasta.example/mcp"},
    {"url": "https://jocasta.example/mcp?token=x"}, {"url": None}, {"command": "/bin/server"},
    {"env": {"TOKEN": "x"}}, {"args": ["x"]},
])
def test_remote_transport_needs_a_public_url_and_no_stdio_fields(tmp_path, params):
    with pytest.raises(Failed):
        call("codex", codex_config=str(tmp_path / "config.toml"), **{**remote("codex"), **params})
    assert not (tmp_path / "config.toml").exists()


def test_stdio_transport_refuses_a_url(tmp_path):
    with pytest.raises(Failed, match="transport: remote"):
        call("codex", codex_config=str(tmp_path / "config.toml"), name="x", command="/bin/x", url=URL)


# The role: laptop-only remote loop over all three providers, stdio unchanged.

def test_role_registers_the_laptop_server_for_claude_and_codex_only(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".config/opencode").mkdir(parents=True)
    codex = home / ".codex/config.toml"
    opencode = home / ".config/opencode/opencode.json"
    claude_json = home / ".claude.json"
    codex.write_text(f'model = "personal"\n[model_providers.private]\nexperimental_bearer_token = "{SECRET}"\n')
    opencode.write_text(json.dumps({"model": "keep", "mcp": {"mine": {"type": "local", "command": ["/keep"]}}}))
    claude_json.write_text(json.dumps({"primaryApiKey": SECRET, "mcpServers": {}}))
    binding = yaml.safe_load(INTERACTIVE.read_text())
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Exercise remote MCP registration in an isolated home",
        "hosts": "localhost", "gather_facts": False,
        "vars": {
            "ansible_connection": "local", "ansible_python_interpreter": sys.executable,
            "fleet_home": str(home), "chaldea_node_version": "26.10.0",
            "mcp_registrations_claude": [FAKE_CLAUDE, "--user-config", str(claude_json)],
        },
        "roles": ["mcp_registrations"],
    }]))
    environment = {**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                   "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible")}

    def run(*extra):
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play), *extra],
                                cwd=tmp_path, env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert SECRET not in result.stdout + result.stderr
        return result.stdout

    def opted(state, providers=None):
        servers = [dict(server, providers=providers or server["providers"])
                   for server in binding["mcp_registrations_remote_servers"]]
        variables = {"mcp_registrations_remote_servers": servers,
                     "mcp_registrations_jocasta_interactive_state": state}
        return ["-e", json.dumps(variables)]

    run()  # Default off: nothing remote anywhere, OpenCode untouched.
    assert "jocasta" not in user_servers(claude_json)
    assert "jocasta" not in tomllib.loads(codex.read_text()).get("mcp_servers", {})
    assert json.loads(opencode.read_text())["mcp"] == {"mine": {"type": "local", "command": ["/keep"]}}

    opencode_before = opencode.read_bytes()
    run(*opted("present"))
    claude_servers = user_servers(claude_json)
    codex_servers = tomllib.loads(codex.read_text())["mcp_servers"]
    assert claude_servers["jocasta"] == {"type": "http", "url": URL, **EXTRA["claude"]}
    assert codex_servers["jocasta"] == {"url": URL, **EXTRA["codex"]}
    # The laptop binding leaves OpenCode off; stdio servers keep their two providers.
    assert opencode.read_bytes() == opencode_before
    assert {"huyang", "ov-memory"} <= set(claude_servers) and {"huyang", "ov-memory"} <= set(codex_servers)
    assert "command" in codex_servers["huyang"] and claude_servers["huyang"]["type"] == "stdio"
    assert json.loads(claude_json.read_text())["primaryApiKey"] == SECRET
    assert re.search(r"changed=0\s", run(*opted("present")))

    # Optional OpenCode opt-in reaches its own config path, and only the remote server.
    run(*opted("present", ["claude", "codex", "opencode"]))
    opencode_servers = json.loads(opencode.read_text())["mcp"]
    assert opencode_servers["jocasta"] == {"type": "remote", "url": URL, **EXTRA["opencode"], "enabled": True}
    assert set(opencode_servers) == {"mine", "jocasta"}

    run(*opted("absent", ["claude", "codex", "opencode"]))
    assert "jocasta" not in user_servers(claude_json)
    assert "jocasta" not in tomllib.loads(codex.read_text())["mcp_servers"]
    assert set(json.loads(opencode.read_text())["mcp"]) == {"mine"}
    assert re.search(r"changed=0\s", run(*opted("absent")))


def test_role_refuses_a_remote_name_shared_with_a_stdio_server(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Refuse a colliding remote name", "hosts": "localhost", "gather_facts": False,
        "vars": {"ansible_connection": "local", "ansible_python_interpreter": sys.executable,
                 "fleet_home": str(home), "chaldea_node_version": "26.10.0",
                 "mcp_registrations_claude": [FAKE_CLAUDE, str(home / "claude.json")],
                 "mcp_registrations_remote_servers": [
                     {"name": "huyang", "url": URL, "providers": ["codex"], "codex": EXTRA["codex"]}]},
        "tasks": [{"name": "Only the remote checks", "ansible.builtin.include_role": {
            "name": "mcp_registrations", "tasks_from": "main"}}],
    }]))
    environment = {**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                   "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible")}
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)], cwd=tmp_path,
                            env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    assert "unique name of its own" in result.stdout + result.stderr
    codex = home / ".codex/config.toml"
    assert "url" not in tomllib.loads(codex.read_text())["mcp_servers"]["huyang"]
