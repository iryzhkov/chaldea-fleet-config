"""Laptop's persistent Jocasta tooling activation, read from the real inventory.

Only the laptop's dedicated host_vars file opts into system waits, the protected
session policy and its fixed provider profiles: the qualified Claude and Codex
profiles and the root-gated OpenCode selection. These tests render the actual
inventory merge, check the exact bound public configuration with the role's own
closed validators, and require every other host to keep its previous settings.
They are source checks only; OpenCode native acceptance belongs to root.
"""
import copy
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_client"
ACTIVATION = ROOT / "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml"
OTHER_HOSTS = ("agent-a", "agent-b", "omarchy-pc", "normandy", "homelab")
HOME = "/home/igor"
ASSETS = HOME + "/.local/share/chaldea/provider-assets"
WORKSPACE = HOME + "/.local/share/chaldea/session-workspaces/jocasta-tooling"
RESOURCE = "https://jocasta.mcp.ryzhkov.dev/mcp"
ISSUER = "https://auth.ryzhkov.dev/application/o/chaldea-jocasta/"
CALLER = "f29ad608-ef74-42e2-bc34-1d8c4f4c8dc5"
PROJECT = "mcp:2fe01b0e-5727-4111-9b95-ff81508562ba"
CLAUDE = "jocasta-tooling-claude"
CODEX = "jocasta-tooling-codex"
OPENCODE = "jocasta-tooling-opencode"
TOOLS = ["get", "history", "list", "search"]
SERVICES = [{"audience": "jocasta", "grants": [{"resource": "project:tooling", "actions": TOOLS}]}]
KEYS = {
    "chaldea_client_waits_enabled", "chaldea_client_waits_service_mode", "chaldea_client_waits_deadline",
    "chaldea_client_waits_environment", "chaldea_client_waits_runtime_root", "chaldea_node_version",
    "chaldea_client_waits_legacy_user_node_version", "chaldea_client_waits_legacy_system_runtime",
    "chaldea_client_session_policy_enabled",
    "chaldea_client_session_ceilings", "chaldea_client_session_presets",
    "chaldea_client_session_enrollments", "chaldea_client_session_profiles", "retention_mise_prune",
}


def activation():
    return yaml.safe_load(ACTIVATION.read_text())


def inventory_vars(host):
    result = subprocess.run(["ansible-inventory", "-i", str(ROOT / "inventory/hosts.yml"), "--host", host],
                            text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def inline_laptop():
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    return hosts["all"]["children"]["agent_hosts"]["hosts"]["laptop"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROLE / "filter_plugins" / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def validate_profiles(values):
    return load("session_profiles").chaldea_session_profiles(
        values["chaldea_client_session_profiles"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_enrollments"], HOME, [])


def with_codex(cwd):
    """The held Codex candidate with the given cwd."""
    values = copy.deepcopy(activation())
    for key in ("chaldea_client_session_presets", "chaldea_client_session_enrollments",
                "chaldea_client_session_profiles"):
        values[key].pop(CODEX)
    preset = copy.deepcopy(values["chaldea_client_session_presets"][CLAUDE])
    preset.update(instanceId="codex-jocasta-tooling", model="gpt-6.1-sol", title="Jocasta tooling read-only Codex",
                  options=[{"id": "reasoningEffort", "value": "high"}])
    values["chaldea_client_session_presets"][CODEX] = preset
    enrollment = copy.deepcopy(values["chaldea_client_session_enrollments"][CLAUDE])
    enrollment.update(username="chaldea-laptop-" + CODEX,
                      secretFile=HOME + "/.config/chaldea/authentik/" + CODEX + ".app-password")
    values["chaldea_client_session_enrollments"][CODEX] = enrollment
    pin = {"sha256": "0" * 64, "size": 1}
    values["chaldea_client_session_profiles"][CODEX] = {
        "driver": "codex", "elf_machine": 183, "model": "gpt-6.1-sol",
        "native": dict(pin, source=ASSETS + "/codex/0.163.0/codex"),
        "host": dict(pin, source=ASSETS + "/codex/0.163.0/codex-code-mode-host"),
        "catalog": dict(pin, source=ASSETS + "/codex/0.163.0/models.json"),
        "home": HOME + "/.cache/acl-codex-startup-f73bc687/home",
        "tmpdir": HOME + "/.local/state/chaldea/profiles/" + CODEX + "/tmp", "cwd": cwd,
        "preset": CODEX, "audience": "jocasta", "server": "jocasta_tooling", "url": RESOURCE,
        "tools": list(TOOLS), "disabled_servers": ["jocasta"]}
    return values


def test_inventory_merge_applies_the_activation_only_to_the_laptop():
    values = activation()
    assert set(values) == KEYS
    # One source of truth: hosts.yml no longer sets any activation key inline.
    inline = inline_laptop()
    assert not set(inline) & KEYS
    laptop = inventory_vars("laptop")
    for key, value in values.items():
        assert laptop[key] == value, key
    for key, value in inline.items():
        assert laptop[key] == value, key
    # Interactive Chaldea MCP stays on its previous config; shared pins stay shared.
    # No declared profile is retired as a side effect.
    assert "mcp_registrations_chaldea_waits_enabled" not in laptop
    assert "chaldea_client_session_profiles_absent" not in laptop
    assert laptop["chaldea_client_version"] == "client-v0.4.11"
    assert laptop["chaldea_client_quota_enabled"] is True
    for host in OTHER_HOSTS:
        other = inventory_vars(host)
        assert other["chaldea_node_version"] == "26.10.0", host
        assert other["chaldea_client_version"] == "client-v0.4.11", host
        for key in KEYS - {"chaldea_node_version", "chaldea_client_waits_enabled", "chaldea_client_waits_environment"}:
            assert key not in other, (host, key)
    pc = inventory_vars("omarchy-pc")
    assert pc["chaldea_client_waits_enabled"] is True
    assert pc["chaldea_client_waits_environment"] == "94023493-6346-46a6-8ca0-3c7d7ef28644"
    for host in ("agent-a", "agent-b", "normandy", "homelab"):
        other = inventory_vars(host)
        assert "chaldea_client_waits_enabled" not in other and "chaldea_client_waits_environment" not in other


def test_activation_binds_the_exact_qualified_claude_configuration():
    values = activation()
    assert values["chaldea_client_waits_enabled"] is True
    assert values["chaldea_client_waits_service_mode"] == "system"
    assert values["chaldea_client_waits_deadline"] == ""
    assert values["chaldea_client_waits_environment"] == "943bead7-d804-4e04-984e-63d230303796"
    assert values["chaldea_client_waits_runtime_root"] == HOME + "/.local/share/chaldea/releases/client-v0.4.20"
    # Admits only the exact unit the previous runtime rendered, for this migration.
    assert values["chaldea_client_waits_legacy_system_runtime"] == HOME + "/.local/share/chaldea/releases/client-v0.4.18"
    assert values["chaldea_node_version"] == "26.12.0"
    assert values["chaldea_client_waits_legacy_user_node_version"] == "26.10.0"
    assert values["retention_mise_prune"] is False
    assert values["chaldea_client_session_policy_enabled"] is True
    assert values["chaldea_client_session_ceilings"] == [
        {"project": "tooling", "maxSeconds": 1800, "destinations": [CALLER], "services": SERVICES}]
    presets = values["chaldea_client_session_presets"]
    # Codex is qualified with cwd bound to the fleet home; OpenCode is selected.
    assert list(presets) == [CLAUDE, CODEX, OPENCODE]
    assert presets[CODEX] == dict(presets[CLAUDE], instanceId="codex-jocasta-tooling", model="gpt-6.1-sol",
                                  title="Jocasta tooling read-only Codex",
                                  options=[{"id": "reasoningEffort", "value": "high"}])
    preset = presets[CLAUDE]
    assert len(preset["prompt"].encode()) == 655
    assert preset == {
        "instanceId": "claude-jocasta-tooling", "model": "claude-opus-5", "runtimeMode": "approval-required",
        "interactionMode": "default", "projectId": PROJECT, "title": "Jocasta tooling read-only Claude",
        "prompt": preset["prompt"], "inputs": {"project": "tooling"}, "project": "tooling",
        "services": SERVICES, "maxSeconds": 1800, "delegate": False, "destinations": [CALLER]}
    assert values["chaldea_client_session_enrollments"] == {name: {
        "form": "app_password", "issuer": ISSUER, "tokenUrl": "https://auth.ryzhkov.dev/application/o/token/",
        "jwksUrl": ISSUER + "jwks/", "clientId": "chaldea-jocasta-tooling",
        "username": "chaldea-laptop-" + name, "scope": "jocasta.read", "resource": RESOURCE,
        "project": "tooling", "maxTokenSeconds": 300,
        "secretFile": HOME + "/.config/chaldea/authentik/" + name + ".app-password"}
        for name in (CLAUDE, CODEX, OPENCODE)}
    codex_home = HOME + "/.cache/acl-codex-startup-f73bc687/home"
    profiles = values["chaldea_client_session_profiles"]
    assert list(profiles) == [CLAUDE, CODEX, OPENCODE]
    assert {name: profiles[name] for name in (CLAUDE, CODEX)} == {CLAUDE: {
        "driver": "claude", "elf_machine": 183, "cwd": WORKSPACE, "preset": CLAUDE, "audience": "jocasta",
        "server": "jocasta_tooling", "url": RESOURCE, "tools": TOOLS,
        "native": {"source": ASSETS + "/claude/2.1.276/claude", "size": 231989488,
                   "sha256": "e9ac3df956083645578a382ad64ec304468666e362c33bfdefd803cd6ff596b0"}},
        CODEX: {
        "driver": "codex", "elf_machine": 183, "model": "gpt-6.1-sol", "home": codex_home,
        "tmpdir": HOME + "/.local/state/chaldea/profiles/" + CODEX + "/tmp", "cwd": HOME,
        "preset": CODEX, "audience": "jocasta", "server": "jocasta_tooling", "url": RESOURCE, "tools": TOOLS,
        "disabled_servers": ["jocasta"],
        "native": {"source": ASSETS + "/codex/0.163.0/codex", "size": 257816200,
                   "sha256": "8a96f66d059d653e68bfd5f3c79337e6f1d7d170d80bf705eb7d0249b34c0ece"},
        "host": {"source": ASSETS + "/codex/0.163.0/codex-code-mode-host", "size": 67118080,
                 "sha256": "255eccc8a5c1d267dc0acbc815cc83aaa1f50955bd99943b29f00cafcdcab771"},
        "catalog": {"source": ASSETS + "/codex/0.163.0/models.json", "size": 65174,
                    "sha256": "ad005892044dec4f817f431ff75302193e27bbfb7533958afe6a91194fd7b784"}}}
    # Stable public paths only: the existing Codex auth HOME is the one cache path.
    for value in strings(values):
        assert "/.cache/" not in value or value == codex_home, value
        assert "/mise/" not in value and "/tmp/" not in value and "release-assets" not in value, value


def retention_command(host):
    """The laptop's real inventory values through the retention unit template."""
    from test_retention_unit import TEMPLATE, exec_start
    import jinja2
    effective = yaml.safe_load((ROOT / "roles/retention/defaults/main.yml").read_text()) | inventory_vars(host)
    env = jinja2.Environment(trim_blocks=True, keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    env.filters["bool"] = bool
    assert isinstance(effective["retention_mise_prune"], bool)
    unit = env.from_string(TEMPLATE.read_text()).render(
        effective | {"retention_script": "/h/.local/bin/chaldea-retention", "retention_worktree_root": "/h/wt",
                     "retention_tmp_dir": "/h/.cache/tmp"})
    return exec_start(unit)


def test_laptop_retention_never_prunes_the_stopped_quota_node():
    # Retention protects only CHALDEA_NODE_VERSION from mise prune, and system mode
    # leaves the laptop's quota and quota-sharing units and the reserved pre-system
    # user unit on Node 26.10.0. With --no-mise-prune the script skips mise prune
    # before running mise at all, so no 26.10.0 install can be removed, whether or
    # not a process holds it. Waits still runs the pinned 26.12.0.
    argv, lines = retention_command("laptop")
    assert argv[-1] == "--no-mise-prune"
    assert "Environment=CHALDEA_NODE_VERSION=26.12.0" in lines
    assert "--worktree-root" in argv and "--tmp-dir" in argv and "--go-cache-max-gb" in argv
    assert inventory_vars("laptop")["chaldea_client_waits_legacy_user_node_version"] == "26.10.0"
    # Every other agent host keeps pruning, protecting its shared 26.10.0 runtime.
    for host in ("agent-a", "agent-b", "omarchy-pc"):
        argv, lines = retention_command(host)
        assert "--no-mise-prune" not in argv, host
        assert "Environment=CHALDEA_NODE_VERSION=26.10.0" in lines, host


def test_opencode_selection_reuses_the_tooling_grant_and_pinned_native():
    values = inventory_vars("laptop")
    # Same prompt, grant, ceiling and destination as Claude; no model options.
    assert values["chaldea_client_session_presets"][OPENCODE] == dict(
        values["chaldea_client_session_presets"][CLAUDE],
        instanceId="opencode-jocasta-tooling", model="opencode/big-pickle",
        title="Jocasta tooling read-only OpenCode")
    assert values["chaldea_client_session_enrollments"][OPENCODE] == dict(
        values["chaldea_client_session_enrollments"][CLAUDE],
        username="chaldea-laptop-" + OPENCODE,
        secretFile=HOME + "/.config/chaldea/authentik/" + OPENCODE + ".app-password")
    # The protected 2.1.3 native with its own private HOME and tmpdir.
    assert values["chaldea_client_session_profiles"][OPENCODE] == {
        "driver": "opencode", "elf_machine": 183, "cwd": HOME, "preset": OPENCODE,
        "home": HOME + "/.local/state/chaldea/profiles/" + OPENCODE + "/home",
        "tmpdir": HOME + "/.local/state/chaldea/profiles/" + OPENCODE + "/tmp",
        "audience": "jocasta", "server": "jocasta_tooling", "url": RESOURCE, "tools": TOOLS,
        "native": {"source": ASSETS + "/opencode/2.1.3/opencode", "size": 236047352,
                   "sha256": "78c279e68f25e69045a7ec5f518fccbad57e8f25d7853e66ba9677ddfaf28b19"}}
    # The only ceiling is still the tooling read grant.
    assert values["chaldea_client_session_ceilings"] == [
        {"project": "tooling", "maxSeconds": 1800, "destinations": [CALLER], "services": SERVICES}]
    for host in OTHER_HOSTS:
        other = inventory_vars(host)
        for short in ("presets", "enrollments", "profiles"):
            assert OPENCODE not in other.get("chaldea_client_session_" + short, {}), host


def test_role_closed_validators_accept_the_activation():
    values = activation()
    load("session_enrollment").chaldea_session_enrollments(
        values["chaldea_client_session_enrollments"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_ceilings"], HOME)
    assert validate_profiles(values)


@pytest.mark.parametrize("field,value", [
    ("tools", ["get", "history", "list", "search", "put"]),
    ("url", "https://jocasta.mcp.ryzhkov.dev/other"),
    ("preset", "jocasta-tooling-undeclared"),
])
def test_role_validator_still_refuses_widened_profiles(field, value):
    values = activation()
    values["chaldea_client_session_profiles"][CLAUDE][field] = value
    with pytest.raises(load("session_profiles").AnsibleFilterError):
        validate_profiles(values)


@pytest.mark.parametrize("cwd", [HOME, WORKSPACE])
def test_codex_candidate_cwd_may_be_the_fleet_home_or_inside_it(cwd):
    assert validate_profiles(with_codex(cwd))


@pytest.mark.parametrize("cwd", [
    "/", "/home", "/home/igorx", "/srv/t3", "/home/igor/", "/home/igor/.", "/home/igor/../igor",
    "//home/igor", "/home/igor//x", "home/igor", "/home/igor/x/..", ""])
def test_codex_candidate_cwd_outside_or_aliasing_the_fleet_home_is_refused(cwd):
    with pytest.raises(load("session_profiles").AnsibleFilterError):
        validate_profiles(with_codex(cwd))


def test_real_inventory_renders_the_protected_policy_through_the_role(tmp_path):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    policy = tmp_path / "policy.json"
    play = tmp_path / "validate.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Validate and render only the laptop's public session policy",
        "hosts": "laptop", "gather_facts": False,
        "tasks": [
            {"name": "Run the role's public policy validation",
             "ansible.builtin.include_role": {"name": "chaldea_client", "tasks_from": "session-policy-public-validate"}},
            {"name": "Run the role's fixed profile validation",
             "ansible.builtin.include_role": {"name": "chaldea_client", "tasks_from": "session-profiles-validate"}},
            {"name": "Render the policy into scratch",
             "ansible.builtin.copy": {
                 "content": "{{ lookup('ansible.builtin.template', '" + str(ROLE / "templates/policy.json.j2") + "') }}",
                 "dest": str(policy), "mode": "0600"}},
        ],
    }]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", "laptop", str(play),
        "--extra-vars", json.dumps({"fleet_home": HOME}),
    ], text=True, capture_output=True, env=env, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    values = activation()
    assert json.loads(policy.read_text()) == {
        "version": 1, "environment": values["chaldea_client_waits_environment"],
        "ceilings": values["chaldea_client_session_ceilings"],
        "presets": values["chaldea_client_session_presets"],
        "enrollments": values["chaldea_client_session_enrollments"]}
