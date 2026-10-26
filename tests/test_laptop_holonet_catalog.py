"""Qualified laptop HoloNet Movies catalog session (host_vars/laptop/chaldea-holonet-catalog.yml).

The HoloNet input is combined into the laptop's effective session maps only
while its flag is true. These tests check its exact closed values and prompt,
that the disabled composition is exactly the Jocasta policy, that enabling adds
only HoloNet and never replaces a Jocasta entry, that the role's validators
refuse widened or shared inputs, and that the actual role delivers the Claude
profile in a scratch tree. Nothing here enables the input on a host, reads a
credential or touches a model login.
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
    ASSETS, CALLER, CLAUDE, HOME, JOCASTA_INPUTS, PROJECT, ROLE, ROOT, SESSION_MAPS, activation,
    effective_laptop, effective_session_maps, inventory_vars, load, strings, validate_profiles)

INPUT = ROOT / "inventory/host_vars/laptop/chaldea-holonet-catalog.yml"
PREFIX = "chaldea_laptop_holonet_catalog_"
FLAG = PREFIX + "enabled"
NAME = "holonet-movies-catalog-claude"
HOLONET_CALLER = "174463d2-8d06-413f-9a09-3fd1c2bbccd3"
SESSION_PROJECT = "mcp:ee3a8c88-8ace-4487-88ec-f19777cc05c2"
MEDIA = "https://media.mcp.ryzhkov.dev/mcp"
ISSUER = "https://auth.ryzhkov.dev/application/o/chaldea-holonet/"
USER = "54b7d36cef804d3c8478474553ed3a82"
GRANT = {"audience": "holonet", "scope": "holonet.read", "holonet_server": "3c86e6d7ff6c4a3296522cdf03d22bb0",
         "holonet_libraries": ["3"], "holonet_catalog_users": [USER], "holonet_history_users": [],
         "holonet_target_users": [], "holonet_actions": ["catalog.read"], "holonet_namespace": "movies-catalog"}
# catalog_query's input keys: user_id, library_id, limit, offset, include_userdata.
CALLS = [
    {"user_id": USER, "library_id": "3", "limit": 3, "offset": 0},
    {"user_id": USER, "library_id": "3", "limit": 1, "offset": 1},
    {"user_id": "f" * 32, "library_id": "3", "limit": 1},
    {"user_id": USER, "library_id": "9223372036854775807", "limit": 1},
    {"user_id": USER, "library_id": "3", "limit": 1, "include_userdata": True},
    {"user_id": USER, "library_id": "3", "limit": 26},
]
DENY = ["mcp__t3-code__*", "mcp__t3_code__*", "Bash", "PowerShell", "Read", "Write", "Edit",
        "Glob", "Grep", "WebFetch", "WebSearch", "Agent"]
Error = load("session_enrollment").AnsibleFilterError


def packet():
    """The HoloNet input maps keyed like the effective session maps."""
    values = yaml.safe_load(INPUT.read_text())
    return {"chaldea_client_session_" + short: values[PREFIX + short] for short in SESSION_MAPS}


def composed(holonet=None):
    """The inventory composition with HoloNet enabled: Jocasta combined last."""
    holonet = packet() if holonet is None else holonet
    values = activation()
    ceilings = "chaldea_client_session_ceilings"
    values[ceilings] = values[ceilings] + holonet[ceilings]
    for key in set(JOCASTA_INPUTS) - {ceilings}:
        values[key] = holonet[key] | values[key]
    return values


def validate(values):
    load("session_enrollment").chaldea_session_enrollments(
        values["chaldea_client_session_enrollments"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_ceilings"], HOME)
    return validate_profiles(values)


def enabled_extra(holonet=None):
    """Extra vars that enable the input, optionally replacing its maps."""
    extra = {FLAG: True}
    for key, value in (holonet or {}).items():
        extra[PREFIX + key.removeprefix("chaldea_client_session_")] = value
    return extra


def test_input_is_enabled_and_binds_the_exact_catalog_only_values():
    values = yaml.safe_load(INPUT.read_text())
    assert set(values) == {FLAG} | {PREFIX + short for short in SESSION_MAPS}
    assert values[FLAG] is True
    holonet = packet()
    assert all(set(holonet["chaldea_client_session_" + short]) == {NAME} for short in SESSION_MAPS[1:])
    assert holonet["chaldea_client_session_ceilings"] == [
        {"project": "holonet-movies", "maxSeconds": 900, "destinations": [HOLONET_CALLER], "services": [GRANT]}]
    preset = holonet["chaldea_client_session_presets"][NAME]
    assert preset == {
        "instanceId": "claude-holonet-movies-catalog", "model": "claude-opus-5",
        "options": [{"id": "effort", "value": "medium"}], "runtimeMode": "approval-required",
        "interactionMode": "default", "projectId": SESSION_PROJECT, "title": "HoloNet Movies catalog read-only Claude",
        "prompt": preset["prompt"], "project": "holonet-movies", "services": [GRANT], "maxSeconds": 900,
        "delegate": False, "destinations": [HOLONET_CALLER]}
    assert holonet["chaldea_client_session_enrollments"][NAME] == GRANT | {
        "form": "app_password", "issuer": ISSUER, "tokenUrl": "https://auth.ryzhkov.dev/application/o/token/",
        "jwksUrl": ISSUER + "jwks/", "clientId": "chaldea-holonet-machine",
        "username": "chaldea-laptop-" + NAME, "resource": MEDIA, "maxTokenSeconds": 300,
        "secretFile": HOME + "/.config/chaldea/authentik/" + NAME + ".app-password"}
    jocasta_claude = activation()["chaldea_client_session_profiles"][CLAUDE]
    assert holonet["chaldea_client_session_profiles"][NAME] == {
        "driver": "claude", "capabilities_probe": True, "native": jocasta_claude["native"], "elf_machine": 183,
        "cwd": HOME + "/.local/share/chaldea/session-workspaces/holonet-movies", "preset": NAME,
        "audience": "holonet", "server": "holonet_catalog", "url": MEDIA, "tools": ["catalog_query"]}
    assert jocasta_claude["native"] == {"source": ASSETS + "/claude/2.1.276/claude", "size": 231989488,
                                        "sha256": "e9ac3df956083645578a382ad64ec304468666e362c33bfdefd803cd6ff596b0"}
    for value in strings(holonet):
        assert "/.cache/" not in value and "/mise/" not in value and "auth.json" not in value, value


def test_bindings_are_actual_and_share_nothing_with_jocasta():
    holonet, jocasta = packet(), activation()
    preset = holonet["chaldea_client_session_presets"][NAME]
    uuid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    assert re.fullmatch("mcp:" + uuid, preset["projectId"]) and re.fullmatch(uuid, HOLONET_CALLER)
    assert preset["projectId"].removeprefix("mcp:") != HOLONET_CALLER
    assert {preset["projectId"], HOLONET_CALLER}.isdisjoint({PROJECT, CALLER})
    for short, field in (("presets", "instanceId"), ("presets", "projectId"), ("presets", "title"),
                         ("presets", "project"), ("enrollments", "username"), ("enrollments", "secretFile"),
                         ("enrollments", "issuer"), ("enrollments", "clientId"), ("enrollments", "resource"),
                         ("profiles", "cwd"), ("profiles", "server"), ("profiles", "url")):
        key = "chaldea_client_session_" + short
        mine = holonet[key][NAME][field]
        assert all(entry.get(field) != mine for entry in jocasta[key].values()), (short, field)
    for short in SESSION_MAPS[1:]:
        key = "chaldea_client_session_" + short
        assert not set(holonet[key]) & set(jocasta[key])
    # Only the laptop carries the input; no other inventory value names it.
    for path in (ROOT / "inventory").rglob("*.yml"):
        if path not in {INPUT, ROOT / "inventory/host_vars/laptop/chaldea-jocasta-tooling.yml"}:
            assert "holonet" not in json.dumps(yaml.safe_load(path.read_text())).lower(), path
    assert inventory_vars("laptop")[FLAG] is True
    for host in ("agent-a", "agent-b", "omarchy-pc", "normandy", "homelab"):
        assert not any(key.startswith(PREFIX) for key in inventory_vars(host)), host


def test_prompt_makes_exactly_the_six_fixed_calls_and_a_bounded_counts_result():
    prompt = packet()["chaldea_client_session_presets"][NAME]["prompt"]
    assert len(prompt.encode()) < 8192
    # Ansible templates inventory strings; the prompt must hold no Jinja delimiter.
    assert not any(token in prompt for token in ("{{", "{%", "{#"))
    calls = re.findall(r"(?<![0-9])([1-6]) (\{[^{}]*\})", prompt)
    assert [int(n) for n, _ in calls] == [1, 2, 3, 4, 5, 6]
    assert [json.loads(body) for _, body in calls] == CALLS
    [summary] = re.findall(r'\{"v":1[^{}]*\}', prompt)
    result = json.loads(summary)
    assert set(result) == {"v", "status", "allowed", "items", "aclDenied", "boundsDenied", "authOrTransport",
                           "other", "userdataAbsent", "onlyCatalogTool", "nativeRenewal", "issues"}
    assert result["nativeRenewal"] == "NOT_EXERCISED"
    assert "under 1024 UTF-8 bytes" in prompt
    for phrase in ('"resource not found"', '"invalid read request"', "authOrTransport and never an ACL",
                   "only catalog_query", "no history or", "holonet_catalog MCP server"):
        assert phrase in prompt, phrase


def test_disabled_effective_maps_are_exactly_the_jocasta_inputs():
    effective, jocasta = effective_session_maps({FLAG: False}), activation()
    for key in JOCASTA_INPUTS:
        assert effective[key] == jocasta[key] and list(effective[key]) == list(jocasta[key]), key
    assert NAME not in json.dumps(effective)
    assert all(s.get("audience") != "holonet" for c in effective["chaldea_client_session_ceilings"]
               for s in c["services"])


def test_enabled_composition_adds_only_holonet_and_keeps_every_jocasta_entry():
    effective, jocasta, holonet = effective_laptop(), activation(), packet()
    assert effective == {key: composed()[key] for key in JOCASTA_INPUTS}
    ceilings = "chaldea_client_session_ceilings"
    assert effective[ceilings] == jocasta[ceilings] + holonet[ceilings]
    for key in set(JOCASTA_INPUTS) - {ceilings}:
        assert set(effective[key]) == set(jocasta[key]) | {NAME}, key
        assert all(effective[key][name] == value for name, value in jocasta[key].items()), key
    assert validate(composed())


def test_a_holonet_name_can_never_replace_a_jocasta_entry():
    holonet = packet()
    for short in SESSION_MAPS[1:]:
        holonet["chaldea_client_session_" + short][CLAUDE] = {"replaced": True}
    effective, jocasta = effective_session_maps(enabled_extra(holonet)), activation()
    for short in SESSION_MAPS[1:]:
        key = "chaldea_client_session_" + short
        assert effective[key][CLAUDE] == jocasta[key][CLAUDE], key


def render(tmp_path, extra):
    """Run the role's public validators over the real laptop inventory and render its policy."""
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    policy = tmp_path / "policy.json"
    play = tmp_path / "validate.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Validate and render the laptop policy with HoloNet enabled",
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
    extra_path = tmp_path / "extra.json"
    extra_path.write_text(json.dumps({"fleet_home": HOME} | extra))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"), ANSIBLE_NOCOLOR="1")
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", "laptop", str(play),
        "--extra-vars", "@" + str(extra_path)], text=True, capture_output=True, env=env, cwd=ROOT)
    return result, policy


def test_enabled_policy_renders_and_validates_through_the_role(tmp_path):
    result, policy = render(tmp_path, enabled_extra())
    assert result.returncode == 0, result.stdout + result.stderr
    values = composed()
    assert json.loads(policy.read_text()) == {
        "version": 1, "environment": values["chaldea_client_waits_environment"],
        "ceilings": values["chaldea_client_session_ceilings"],
        "presets": values["chaldea_client_session_presets"],
        "enrollments": values["chaldea_client_session_enrollments"]}
    assert len(policy.read_bytes()) < 64 * 1024


def test_enabling_a_widened_grant_is_refused_by_the_role_before_any_write(tmp_path):
    holonet = packet()
    holonet["chaldea_client_session_enrollments"][NAME]["holonet_history_users"] = [USER]
    result, policy = render(tmp_path, enabled_extra(holonet))
    assert result.returncode != 0
    # The closed validator's own refusal, reported by its assert task.
    output = result.stdout + result.stderr
    assert "Require each enrollment to match its preset" in output, output
    assert "HoloNet catalog-only" in output or "closed service contract" in output, output
    assert not policy.exists()


def _preset(holonet, **change):
    holonet["chaldea_client_session_presets"][NAME].update(change)


def _grant(holonet, **change):
    """Change the grant in all three places, so only the ceiling or contract can refuse it."""
    grant = dict(GRANT, **change)
    holonet["chaldea_client_session_presets"][NAME]["services"] = [grant]
    holonet["chaldea_client_session_ceilings"][0]["services"] = [copy.deepcopy(grant)]
    holonet["chaldea_client_session_enrollments"][NAME].update(change)


def _enrollment(holonet, **change):
    holonet["chaldea_client_session_enrollments"][NAME].update(change)


def _profile(holonet, **change):
    holonet["chaldea_client_session_profiles"][NAME].update(change)


JOCASTA = activation()["chaldea_client_session_enrollments"][CLAUDE]


@pytest.mark.parametrize("mutate", [
    pytest.param(lambda h: _grant(h, holonet_history_users=[USER]), id="history-user"),
    pytest.param(lambda h: _grant(h, holonet_target_users=[USER]), id="target-user"),
    pytest.param(lambda h: _grant(h, holonet_actions=["catalog.read", "userdata.read"]), id="userdata-action"),
    pytest.param(lambda h: _grant(h, holonet_libraries=["3", "4"]), id="second-library"),
    pytest.param(lambda h: _grant(h, holonet_catalog_users=[USER, "f" * 32]), id="second-user"),
    pytest.param(lambda h: _grant(h, scope="holonet.read holonet.write"), id="write-scope"),
    pytest.param(lambda h: _preset(h, services=[dict(GRANT, holonet_libraries=["4"])]), id="other-library"),
    pytest.param(lambda h: _preset(h, maxSeconds=901), id="longer"),
    pytest.param(lambda h: _preset(h, destinations=[HOLONET_CALLER, CALLER]), id="jocasta-caller"),
    pytest.param(lambda h: _preset(h, project="tooling"), id="tooling-project"),
    pytest.param(lambda h: _preset(h, services=[GRANT, {"audience": "jocasta", "grants": [
        {"resource": "project:tooling", "actions": ["get"]}]}]), id="second-service"),
    pytest.param(lambda h: h["chaldea_client_session_enrollments"].pop(NAME), id="no-enrollment"),
    pytest.param(lambda h: _enrollment(h, holonet_namespace="tv-catalog"), id="enrollment-namespace"),
    pytest.param(lambda h: _enrollment(h, username=JOCASTA["username"]), id="jocasta-account"),
    pytest.param(lambda h: _enrollment(h, secretFile=JOCASTA["secretFile"]), id="jocasta-secret"),
    pytest.param(lambda h: _enrollment(h, clientId=JOCASTA["clientId"]), id="jocasta-client"),
    pytest.param(lambda h: _enrollment(h, issuer=JOCASTA["issuer"], jwksUrl=JOCASTA["jwksUrl"]), id="jocasta-issuer"),
    pytest.param(lambda h: _enrollment(h, resource=JOCASTA["resource"]), id="jocasta-resource"),
    pytest.param(lambda h: _enrollment(h, maxTokenSeconds=3600), id="long-token"),
    pytest.param(lambda h: _profile(h, url=JOCASTA["resource"]), id="profile-url"),
    pytest.param(lambda h: _profile(h, audience="jocasta"), id="profile-audience"),
    pytest.param(lambda h: _profile(h, preset="holonet-undeclared"), id="profile-preset"),
    pytest.param(lambda h: _profile(h, server="t3-code"), id="profile-t3-server"),
    pytest.param(lambda h: _profile(h, tools=[]), id="profile-no-tools"),
    pytest.param(lambda h: _profile(h, home=HOME + "/.local/state/chaldea/profiles/" + NAME), id="profile-home"),
])
def test_role_validators_refuse_widened_shared_or_incomplete_inputs(mutate):
    holonet = packet()
    mutate(holonet)
    with pytest.raises(Error):
        validate(composed(holonet))


def test_actual_role_delivers_the_holonet_claude_profile(tmp_path, monkeypatch):
    from test_chaldea_session_profiles import PRESET, ok, run
    from test_chaldea_session_profiles_claude import claude_layout, launch, t3_args

    case = claude_layout(tmp_path, monkeypatch)
    holonet = packet()
    # Native, ELF machine and cwd are the scratch fixture's; the preset, grant,
    # enrollment, audience, server, URL and tools are the input's own values.
    preset = dict(holonet["chaldea_client_session_presets"][NAME], model="fixture-model")
    enrollment = dict(holonet["chaldea_client_session_enrollments"][NAME],
                      secretFile=str(case.home / ".config/chaldea/authentik" / (NAME + ".app-password")))
    profile = dict(holonet["chaldea_client_session_profiles"][NAME],
                   **{k: case.claude[k] for k in ("native", "elf_machine", "cwd")})
    variables = case.variables
    variables["chaldea_client_session_ceilings"] = (
        variables["chaldea_client_session_ceilings"] + holonet["chaldea_client_session_ceilings"])
    variables["chaldea_client_session_presets"] = variables["chaldea_client_session_presets"] | {NAME: preset}
    variables["chaldea_client_session_enrollments"] = (
        variables["chaldea_client_session_enrollments"] | {NAME: enrollment})
    variables["chaldea_client_session_profiles"] = {NAME: profile}
    case.claude_dir = case.directory.parent / NAME
    case.mcp = str(case.claude_dir / "mcp.json")
    helper = case.helper.replace(f"--preset {PRESET} --audience jocasta", f"--preset {NAME} --audience holonet")
    assert helper != case.helper

    ok(run(case, check=True))
    assert not case.claude_dir.exists()
    ok(run(case))
    assert sorted(p.name for p in case.claude_dir.iterdir()) == ["claude", "claude-settings.json", "exec", "mcp.json"]
    assert json.loads((case.claude_dir / "claude-settings.json").read_text()) == {"permissions": {
        "allow": ["mcp__holonet_catalog__catalog_query"], "deny": DENY}}
    assert json.loads((case.claude_dir / "mcp.json").read_text()) == {"mcpServers": {"holonet_catalog": {
        "type": "http", "url": MEDIA, "headersHelper": helper}}}
    # No home write: the Codex fixture home holds only its untouched FIFO.
    assert sorted(p.name for p in (case.profile_home / ".codex").iterdir()) == ["auth.json"]
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    # The stock T3 argv with the preset's medium effort is admitted and corrected.
    launched = launch(case, t3_args(case, extra=("--effort", "medium")))
    assert launched.returncode == 0, launched.stderr
    assert "mcp__holonet_catalog__catalog_query" in launched.stdout
    assert launched.stdout.rstrip("\n").endswith("--effort medium")
