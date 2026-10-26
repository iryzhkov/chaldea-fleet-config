"""Prepared limited OpenCode selections for agent-a, agent-b and omarchy-pc.

The prepared data (docs/examples/opencode-fleet-limited.yml) is outside
inventory. These tests check that it stays inert, that composing a host's
selection refuses unpopulated, malformed, shared or laptop-copied bindings,
that the composed selection is the laptop's reviewed OpenCode shape with only
the host-local facts changed, and that the role's own validators, policy
render and profile delivery accept it. The bindings used here are explicit
test-only IDs, never real host metadata. Nothing here reads a credential,
contacts an issuer or touches a host.
"""
import copy
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from test_laptop_jocasta_tooling import (
    ASSETS, CALLER, HOME, OPENCODE as NAME, PROJECT, RESOURCE, ROLE, ROOT, SERVICES, TOOLS, activation,
    effective_laptop, inventory_vars, load, strings)

CANDIDATE = ROOT / "docs/examples/opencode-fleet-limited.yml"
HOSTS = ("agent-a", "agent-b", "omarchy-pc")
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PATTERNS = {"waits_environment": UUID, "caller_destination": "(mcp:)?" + UUID, "session_project": "(mcp:)?" + UUID}
PC_ENVIRONMENT = "94023493-6346-46a6-8ca0-3c7d7ef28644"
LAPTOP_IDS = {CALLER, PROJECT, activation()["chaldea_client_waits_environment"]}
SESSION_KEYS = {"chaldea_client_session_ceilings", "chaldea_client_session_presets",
                "chaldea_client_session_enrollments", "chaldea_client_session_profiles"}
KEYS = SESSION_KEYS | {
    "chaldea_client_waits_enabled", "chaldea_client_waits_service_mode", "chaldea_client_waits_deadline",
    "chaldea_client_waits_runtime_root", "chaldea_client_session_policy_enabled"}
X64 = {"source": ASSETS + "/opencode/2.1.3/opencode", "size": 240306352,
       "sha256": "4c2630769fa853343a781e765b2280fc1a07f33f7c10d484f75d59e61eb85bc3"}
Error = load("session_enrollment").AnsibleFilterError


def fixture_id(host, slot, prefix=""):
    """An explicit, obviously synthetic ID, distinct per host and slot."""
    return prefix + "00000000-0000-4000-8000-%012x" % (HOSTS.index(host) * 16 + slot + 0xf1000)


# Test-only bindings. Real values come from each host's own T3 server at root
# integration and replace these nowhere in source except that host's inventory.
FIXTURE = {host: {"caller_destination": fixture_id(host, 1), "session_project": fixture_id(host, 2, "mcp:")}
           | ({} if host == "omarchy-pc" else {"waits_environment": fixture_id(host, 0)}) for host in HOSTS}


class Unbound(ValueError):
    """A selection was composed from a missing, malformed or copied binding."""


def candidate():
    return yaml.safe_load(CANDIDATE.read_text())


def compose(host, bindings, packet=None):
    """One host's inventory selection, refusing anything but its own exact bindings."""
    packet = candidate() if packet is None else packet
    if host not in packet["bindings"] or set(bindings) != set(packet["bindings"][host]):
        raise Unbound(host + ": bindings must be exactly " + ", ".join(sorted(packet["bindings"].get(host, {}))))
    for key, value in bindings.items():
        if not isinstance(value, str) or re.fullmatch(PATTERNS[key], value, re.ASCII) is None:
            raise Unbound(host + ": " + key + " is unpopulated or malformed")
        if value in LAPTOP_IDS or value.removeprefix("mcp:") in {i.removeprefix("mcp:") for i in LAPTOP_IDS}:
            raise Unbound(host + ": " + key + " is a laptop ID")
    if bindings["caller_destination"].removeprefix("mcp:") == bindings["session_project"].removeprefix("mcp:"):
        raise Unbound(host + ": caller and session projects must differ")
    selection = copy.deepcopy(packet["selection"])
    services = selection["ceiling"]["services"]
    destinations = [bindings["caller_destination"]]
    values = {key: selection[key] for key in KEYS - SESSION_KEYS}
    if "waits_environment" in bindings:
        values["chaldea_client_waits_environment"] = bindings["waits_environment"]
    values["chaldea_client_session_ceilings"] = [dict(selection["ceiling"], destinations=destinations)]
    values["chaldea_client_session_presets"] = {NAME: dict(
        selection["preset"], projectId=bindings["session_project"], services=services, destinations=destinations)}
    values["chaldea_client_session_enrollments"] = {NAME: dict(
        selection["enrollment"], username="chaldea-" + host + "-" + NAME)}
    values["chaldea_client_session_profiles"] = {NAME: selection["profile"]}
    return values


def compose_all(bindings, packet=None):
    """Every host's selection; no binding value may be shared between hosts."""
    seen = [v for host in HOSTS for v in bindings[host].values()]
    if len({v.removeprefix("mcp:") if isinstance(v, str) else v for v in seen}) != len(seen):
        raise Unbound("bindings must be distinct across hosts")
    return {host: compose(host, bindings[host], packet) for host in HOSTS}


def validate(values):
    load("session_enrollment").chaldea_session_enrollments(
        values["chaldea_client_session_enrollments"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_ceilings"], HOME)
    return load("session_profiles").chaldea_session_profiles(
        values["chaldea_client_session_profiles"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_enrollments"], HOME, [])


def test_prepared_data_is_inert_and_every_binding_is_unpopulated():
    packet = candidate()
    assert set(packet) == {"bindings", "selection"}
    assert list(packet["bindings"]) == list(HOSTS)
    assert {host: set(packet["bindings"][host]) for host in HOSTS} == {host: set(FIXTURE[host]) for host in HOSTS}
    assert all(value is None for host in HOSTS for value in packet["bindings"][host].values())
    for host in HOSTS:
        with pytest.raises(Unbound):
            compose(host, packet["bindings"][host], packet)
    for path in (ROOT / "inventory").rglob("*"):
        if path.is_file() and path != ROOT / "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml":
            assert NAME not in path.read_text(errors="replace"), path
    for host in HOSTS:
        assert not (ROOT / "inventory/host_vars" / host / "chaldea-jocasta-tooling.yml").exists()
        current = inventory_vars(host)
        assert current["chaldea_node_version"] == "26.10.0" and current["chaldea_client_version"] == "client-v0.4.11"
        for key in SESSION_KEYS | {"chaldea_client_waits_service_mode", "chaldea_client_waits_runtime_root",
                                   "chaldea_client_session_policy_enabled",
                                   "chaldea_client_waits_legacy_user_node_version", "retention_mise_prune"}:
            assert key not in current, (host, key)
    # The laptop keeps its three Jocasta profiles plus qualified HoloNet.
    laptop = effective_laptop()
    for short in ("presets", "enrollments", "profiles"):
        assert list(laptop["chaldea_client_session_" + short]) == [
            "holonet-movies-catalog-claude", "jocasta-tooling-claude", "jocasta-tooling-codex", NAME]


def _set(host, key, value):
    def apply(bindings):
        bindings[host][key] = value
    return apply


@pytest.mark.parametrize("change", [
    pytest.param(None, id="prepared-nulls"),
    pytest.param(_set("agent-a", "waits_environment", ""), id="empty-environment"),
    pytest.param(_set("agent-b", "caller_destination", "TODO"), id="placeholder-caller"),
    pytest.param(_set("agent-a", "session_project", "mcp:" + "0" * 31), id="malformed-project"),
    pytest.param(_set("omarchy-pc", "caller_destination", CALLER), id="laptop-caller"),
    pytest.param(_set("agent-b", "session_project", PROJECT), id="laptop-project"),
    pytest.param(_set("agent-a", "session_project", PROJECT.removeprefix("mcp:")), id="laptop-project-bare"),
    pytest.param(_set("agent-a", "waits_environment", activation()["chaldea_client_waits_environment"]),
                 id="laptop-environment"),
    pytest.param(_set("omarchy-pc", "waits_environment", fixture_id("omarchy-pc", 0)), id="pc-environment-override"),
    pytest.param(lambda b: b["agent-b"].pop("waits_environment"), id="missing-environment"),
    pytest.param(_set("agent-b", "caller_destination", fixture_id("agent-a", 1)), id="shared-caller"),
    pytest.param(_set("agent-a", "session_project", fixture_id("agent-a", 1, "mcp:")), id="caller-is-session"),
])
def test_composition_refuses_unpopulated_shared_or_copied_bindings(change):
    if change is None:
        bindings = candidate()["bindings"]
    else:
        bindings = copy.deepcopy(FIXTURE)
        change(bindings)
    with pytest.raises(Unbound):
        compose_all(bindings)


def test_composed_selection_is_the_laptop_opencode_shape_with_only_host_facts_changed():
    laptop = activation()
    selections = compose_all(FIXTURE)
    for host, values in selections.items():
        bound = FIXTURE[host]
        assert set(values) == KEYS | ({"chaldea_client_waits_environment"} if host != "omarchy-pc" else set())
        assert (values["chaldea_client_waits_enabled"], values["chaldea_client_waits_service_mode"],
                values["chaldea_client_waits_deadline"], values["chaldea_client_session_policy_enabled"]) == (
            True, "system", "", True)
        assert values["chaldea_client_waits_runtime_root"] == laptop["chaldea_client_waits_runtime_root"]
        destinations = [bound["caller_destination"]]
        assert values["chaldea_client_session_ceilings"] == [
            {"project": "tooling", "maxSeconds": 1800, "destinations": destinations, "services": SERVICES}]
        # Exactly one preset, enrollment and profile: never Claude or Codex.
        assert {short: list(values["chaldea_client_session_" + short]) for short in ("presets", "enrollments", "profiles")} \
            == {"presets": [NAME], "enrollments": [NAME], "profiles": [NAME]}
        assert values["chaldea_client_session_presets"][NAME] == dict(
            laptop["chaldea_client_session_presets"][NAME], projectId=bound["session_project"], destinations=destinations)
        assert values["chaldea_client_session_enrollments"][NAME] == dict(
            laptop["chaldea_client_session_enrollments"][NAME], username="chaldea-" + host + "-" + NAME)
        profile = values["chaldea_client_session_profiles"][NAME]
        assert profile == dict(laptop["chaldea_client_session_profiles"][NAME], native=X64, elf_machine=62)
        assert profile["native"]["sha256"] != laptop["chaldea_client_session_profiles"][NAME]["native"]["sha256"]
        assert values["chaldea_client_session_enrollments"][NAME]["secretFile"] == (
            HOME + "/.config/chaldea/authentik/jocasta-tooling-opencode.app-password")
        for value in strings(values):
            assert value not in LAPTOP_IDS and "laptop" not in value, value
            assert "/.cache/" not in value and "/mise/" not in value and "/tmp/" not in value, value
        # Nothing else the host already declares is changed: no interactive
        # Jocasta, MCP registration, Node, retention or client key, and the
        # one inline key it shares (omarchy-pc's waits switch) keeps its value.
        interactive = yaml.safe_load((ROOT / "inventory/host_vars" / host / "jocasta-interactive.yml").read_text())
        assert not set(values) & set(interactive)
        inline = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"][host]
        assert all(inline[key] == values[key] for key in set(values) & set(inline))
        assert set(values) & set(inline) == ({"chaldea_client_waits_enabled"} if host == "omarchy-pc" else set())
    usernames = [v["chaldea_client_session_enrollments"][NAME]["username"] for v in selections.values()]
    assert usernames == ["chaldea-agent-a-jocasta-tooling-opencode", "chaldea-agent-b-jocasta-tooling-opencode",
                         "chaldea-omarchy-pc-jocasta-tooling-opencode"]


@pytest.mark.parametrize("host", HOSTS)
def test_role_closed_validators_accept_each_composed_host(host):
    assert validate(compose_all(FIXTURE)[host])


def _preset(**change):
    return lambda v: v["chaldea_client_session_presets"][NAME].update(change)


def _enrollment(**change):
    return lambda v: v["chaldea_client_session_enrollments"][NAME].update(change)


def _profile(**change):
    return lambda v: v["chaldea_client_session_profiles"][NAME].update(change)


@pytest.mark.parametrize("mutate", [
    _preset(services=[{"audience": "jocasta", "grants": [{"resource": "project:homelab", "actions": TOOLS}]}]),
    _enrollment(project="homelab"),
    _enrollment(scope="jocasta.write"),
    _enrollment(maxTokenSeconds=3600),
    _enrollment(secretFile=HOME + "/.config/chaldea/authentik/jocasta-tooling-claude.app-password"),
    _profile(tools=TOOLS + ["put"]),
    _profile(url="https://jocasta.mcp.ryzhkov.dev/other"),
    _profile(preset="jocasta-tooling-undeclared"),
    _profile(elf_machine=40),
    _profile(native=dict(X64, size=400000001)),
    _profile(home=HOME),
    _profile(tmpdir=HOME + "/.local/state/chaldea/profiles/jocasta-tooling-opencode/home"),
    _profile(server="t3_code"),
])
def test_role_validators_refuse_widened_composed_selections(mutate):
    values = compose_all(FIXTURE)["agent-a"]
    mutate(values)
    with pytest.raises(Error):
        validate(values)


@pytest.mark.parametrize("host", HOSTS)
def test_real_inventory_renders_each_host_policy_through_the_role(tmp_path, host):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    values = compose_all(FIXTURE)[host]
    policy = tmp_path / "policy.json"
    play = tmp_path / "validate.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Validate and render one host's composed limited OpenCode policy",
        "hosts": host, "gather_facts": False,
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
    extra_path = tmp_path / "selection.json"
    extra_path.write_text(json.dumps({"fleet_home": HOME} | values))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", host, str(play),
        "--extra-vars", "@" + str(extra_path)], text=True, capture_output=True, env=env, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    environment = values.get("chaldea_client_waits_environment", PC_ENVIRONMENT)
    assert host != "omarchy-pc" or inventory_vars(host)["chaldea_client_waits_environment"] == PC_ENVIRONMENT
    assert json.loads(policy.read_text()) == {
        "version": 1, "environment": environment,
        "ceilings": values["chaldea_client_session_ceilings"],
        "presets": values["chaldea_client_session_presets"],
        "enrollments": values["chaldea_client_session_enrollments"]}


def test_inventory_render_refuses_a_selection_without_a_waits_environment(tmp_path):
    # agent-a declares no environment in source: an unbound selection stops the
    # role's own public validation before any write.
    values = compose_all(FIXTURE)["agent-a"]
    values.pop("chaldea_client_waits_environment")
    play = tmp_path / "validate.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Validate an unbound selection", "hosts": "agent-a", "gather_facts": False,
        "tasks": [{"name": "Run the role's public policy validation", "ansible.builtin.include_role": {
            "name": "chaldea_client", "tasks_from": "session-policy-public-validate"}}]}]))
    extra_path = tmp_path / "selection.json"
    extra_path.write_text(json.dumps({"fleet_home": HOME} | values))
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", "agent-a", str(play),
        "--extra-vars", "@" + str(extra_path)], text=True, capture_output=True,
        env=dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles")), cwd=ROOT)
    assert result.returncode != 0
    assert "needs waits enabled with its environment" in result.stdout, result.stdout[-6000:]


@pytest.mark.parametrize("machine,launches", [(62, True), (183, False)])
def test_actual_role_delivers_the_composed_profile_and_its_launcher_checks_the_machine(
        tmp_path, monkeypatch, machine, launches):
    from test_chaldea_session_profiles import ok, run
    from test_chaldea_session_profiles_opencode import opencode_layout

    case = opencode_layout(tmp_path, monkeypatch)
    if case.opencode["elf_machine"] != 62:
        pytest.skip("needs an x86-64 job host: the scratch native is the host's bash")
    values = compose_all(FIXTURE)["agent-a"]
    variables = case.variables
    # The scratch fixture supplies the native bytes, private directories and
    # T3 server directory; preset, grant, enrollment, server, URL and tools are
    # the composed selection's own values.
    enrollment = dict(values["chaldea_client_session_enrollments"][NAME],
                      secretFile=str(case.home / ".config/chaldea/authentik" / (NAME + ".app-password")))
    profile = dict(values["chaldea_client_session_profiles"][NAME], elf_machine=machine,
                   **{k: case.opencode[k] for k in ("native", "home", "tmpdir", "cwd")})
    variables["chaldea_client_session_ceilings"] = (
        variables["chaldea_client_session_ceilings"] + values["chaldea_client_session_ceilings"])
    variables["chaldea_client_session_presets"] = (
        variables["chaldea_client_session_presets"] | values["chaldea_client_session_presets"])
    variables["chaldea_client_session_enrollments"] = variables["chaldea_client_session_enrollments"] | {NAME: enrollment}
    variables["chaldea_client_session_profiles"] = {NAME: profile}
    directory = case.opencode_dir.parent / NAME
    ok(run(case))
    assert sorted(p.name for p in directory.iterdir()) == ["exec", "opencode", "opencode.json"]
    config = json.loads((directory / "opencode.json").read_text())
    assert config["mcp"] == {"jocasta_tooling": {
        "type": "remote", "url": RESOURCE, "oauth": False, "enabled": True,
        "headers": {"Authorization": "{file:jocasta.authorization}"}}}
    assert list(case.opencode_home.iterdir()) == [] and list(case.runtime.iterdir()) == []
    version = subprocess.run([str(directory / "exec"), "--version"], cwd=case.home, env={"PATH": "/usr/bin:/bin"},
                             capture_output=True, text=True, timeout=30)
    if launches:
        assert version.returncode == 0 and "bash" in version.stdout, version
    else:
        # A native for another machine is refused before it runs.
        assert version.returncode != 0 and "bash" not in version.stdout, version
    assert list(case.runtime.iterdir()) == []
