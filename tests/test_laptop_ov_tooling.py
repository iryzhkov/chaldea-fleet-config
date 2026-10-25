"""Inert laptop OV tooling candidate (docs/examples/laptop-ov-tooling-codex.yml).

The candidate is outside inventory. These tests check its exact closed values,
run the role's own public validators over the laptop's real maps with the
candidate merged, render the protected policy from the real inventory, and
deliver the profile through the actual role in a scratch tree. Nothing here
enables the candidate, reads a credential or touches a model login.
"""
import copy
import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from test_laptop_jocasta_tooling import (
    ASSETS, CALLER, CODEX, HOME, PROJECT, ROLE, ROOT, activation, inventory_vars, load, strings, validate_profiles)

CANDIDATE = ROOT / "docs/examples/laptop-ov-tooling-codex.yml"
NAME = "ov-tooling-codex"
NODE = "viking://resources/homeassistant-api/rest-api.md"
SIBLING = "viking://resources/homeassistant-api/ov-canary-denied-a63e197f"
OV_URL = "https://ov.mcp.ryzhkov.dev/mcp"
ISSUER = "https://auth.ryzhkov.dev/application/o/ov-http-a63e197f/"
SERVICE = {"audience": "ov", "scope": "ov.read", "ov_namespaces": [NODE]}
MAPS = ("presets", "enrollments", "profiles")
DISABLED = ["chaldea", "huyang", "jocasta", "ov-memory"]
Error = load("session_enrollment").AnsibleFilterError


def candidate():
    return yaml.safe_load(CANDIDATE.read_text())


def merged(packet=None):
    """The laptop's real maps with the candidate added, as root would merge them."""
    packet = copy.deepcopy(candidate() if packet is None else packet)
    values = activation()
    values["chaldea_client_session_ceilings"] = values["chaldea_client_session_ceilings"] + packet["ceilings"]
    for short in MAPS:
        key = "chaldea_client_session_" + short
        values[key] = values[key] | packet[short]
    return values


def validate(values):
    load("session_enrollment").chaldea_session_enrollments(
        values["chaldea_client_session_enrollments"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_ceilings"], HOME)
    return validate_profiles(values)


def test_candidate_is_inactive_and_merging_preserves_every_existing_entry():
    packet = candidate()
    assert set(packet) == {"ceilings", *MAPS}
    assert all(set(packet[short]) == {NAME} for short in MAPS)
    laptop = inventory_vars("laptop")
    for short in MAPS:
        assert NAME not in laptop["chaldea_client_session_" + short]
    assert all(s.get("audience") != "ov" for c in laptop["chaldea_client_session_ceilings"] for s in c["services"])
    for path in (ROOT / "inventory").rglob("*"):
        if path.is_file():
            assert "ov-tooling" not in path.read_text(errors="replace"), path
    before, after = activation(), merged()
    assert after["chaldea_client_session_ceilings"][:-1] == before["chaldea_client_session_ceilings"]
    for short in MAPS:
        key = "chaldea_client_session_" + short
        assert {k: v for k, v in after[key].items() if k != NAME} == before[key]


def test_candidate_binds_one_exact_closed_ov_grant():
    packet = candidate()
    assert packet["ceilings"] == [{"project": "tooling", "maxSeconds": 900, "destinations": [CALLER],
                                   "services": [SERVICE]}]
    preset = packet["presets"][NAME]
    codex = {k: v for k, v in activation()["chaldea_client_session_presets"][CODEX].items() if k != "inputs"}
    assert preset == dict(codex, instanceId="codex-ov-tooling", title="OV tooling metadata-only Codex",
                          prompt=preset["prompt"], services=[SERVICE], maxSeconds=900)
    assert (preset["model"], preset["options"], preset["projectId"], preset["delegate"]) == (
        "gpt-6.1-sol", [{"id": "reasoningEffort", "value": "high"}], PROJECT, False)
    prompt = preset["prompt"]
    assert len(prompt.encode()) < 1000
    assert NODE in prompt and SIBLING in prompt and "memory_stat" in prompt
    assert '"renewal":"NOT_RUN"' in prompt and "do not wait or sleep" in prompt
    assert packet["enrollments"][NAME] == {
        "form": "app_password", "audience": "ov", "issuer": ISSUER,
        "tokenUrl": "https://auth.ryzhkov.dev/application/o/token/", "jwksUrl": ISSUER + "jwks/",
        "clientId": "ov-http-a63e197f-machine", "username": "chaldea-laptop-" + NAME, "scope": "ov.read",
        "ov_namespaces": [NODE], "resource": OV_URL, "maxTokenSeconds": 300,
        "secretFile": HOME + "/.config/chaldea/authentik/" + NAME + ".app-password"}
    jocasta_profile = activation()["chaldea_client_session_profiles"][CODEX]
    profile = packet["profiles"][NAME]
    assert profile == dict(
        jocasta_profile, home=HOME + "/.local/state/chaldea/profiles/" + NAME + "/home",
        tmpdir=HOME + "/.local/state/chaldea/profiles/" + NAME + "/tmp", preset=NAME, audience="ov",
        server="ov_tooling", url=OV_URL, tools=["memory_stat"], disabled_servers=DISABLED)
    assert profile["native"]["source"].startswith(ASSETS + "/codex/0.163.0/")
    assert profile["home"] != jocasta_profile["home"]
    for value in strings(packet):
        assert "/.cache/" not in value and "/mise/" not in value and "auth.json" not in value, value


def test_role_closed_validators_accept_the_merged_laptop_maps():
    assert validate(merged())


def _preset(packet, **change):
    packet["presets"][NAME].update(change)


def _service(packet, roots):
    service = dict(SERVICE, ov_namespaces=roots)
    packet["presets"][NAME]["services"] = [service]
    packet["enrollments"][NAME]["ov_namespaces"] = roots


def _enrollment(packet, **change):
    packet["enrollments"][NAME].update(change)


def _profile(packet, **change):
    packet["profiles"][NAME].update(change)


JOCASTA = activation()["chaldea_client_session_enrollments"][CODEX]


@pytest.mark.parametrize("mutate", [
    lambda p: _service(p, ["viking://resources/homeassistant-api"]),
    lambda p: _service(p, ["viking://resources"]),
    lambda p: _service(p, [NODE, "viking://resources/other"]),
    lambda p: _service(p, [SIBLING]),
    lambda p: _preset(p, maxSeconds=901),
    lambda p: _preset(p, destinations=[CALLER, "another-caller-project"]),
    lambda p: _preset(p, project="homelab"),
    lambda p: _preset(p, services=[SERVICE, {"audience": "jocasta", "grants": [
        {"resource": "project:tooling", "actions": ["get"]}]}]),
    lambda p: _enrollment(p, ov_namespaces=["viking://resources/homeassistant-api"]),
    lambda p: _enrollment(p, scope="ov.write"),
    lambda p: _enrollment(p, username=JOCASTA["username"]),
    lambda p: _enrollment(p, secretFile=JOCASTA["secretFile"]),
    lambda p: _enrollment(p, clientId=JOCASTA["clientId"]),
    lambda p: _enrollment(p, issuer=JOCASTA["issuer"], jwksUrl=JOCASTA["jwksUrl"]),
    lambda p: _enrollment(p, resource=JOCASTA["resource"]),
    lambda p: _enrollment(p, maxTokenSeconds=3600),
    lambda p: _profile(p, url=JOCASTA["resource"]),
    lambda p: _profile(p, home=activation()["chaldea_client_session_profiles"][CODEX]["home"]),
    lambda p: _profile(p, disabled_servers=DISABLED + ["ov_tooling"]),
    lambda p: _profile(p, preset="ov-tooling-undeclared"),
    lambda p: _profile(p, model="gpt-6.1-luna"),
])
def test_role_validators_refuse_widened_or_shared_candidates(mutate):
    packet = candidate()
    mutate(packet)
    with pytest.raises(Error):
        validate(merged(packet))


def test_real_inventory_renders_the_merged_policy_through_the_role(tmp_path):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    values = merged()
    policy = tmp_path / "policy.json"
    play = tmp_path / "validate.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Validate and render the laptop policy with the OV candidate merged",
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
    extra = {"fleet_home": HOME} | {key: values[key] for key in (
        "chaldea_client_session_ceilings", "chaldea_client_session_presets",
        "chaldea_client_session_enrollments", "chaldea_client_session_profiles")}
    extra_path = tmp_path / "candidate.json"
    extra_path.write_text(json.dumps(extra))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", "laptop", str(play),
        "--extra-vars", "@" + str(extra_path)], text=True, capture_output=True, env=env, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = json.loads(policy.read_text())
    assert rendered == {
        "version": 1, "environment": values["chaldea_client_waits_environment"],
        "ceilings": values["chaldea_client_session_ceilings"],
        "presets": values["chaldea_client_session_presets"],
        "enrollments": values["chaldea_client_session_enrollments"]}
    assert len(policy.read_bytes()) < 64 * 1024


def test_actual_role_delivers_the_ov_profile_with_its_closed_server(tmp_path, monkeypatch):
    from test_chaldea_session_profiles import PRESET, launch, layout, ok, run

    case = layout(tmp_path, monkeypatch)
    packet = candidate()
    home = case.home
    variables = case.variables
    # Binaries, model, home and paths are the scratch fixture's; the preset,
    # grant, enrollment, server, URL, tools and neutralized servers are the
    # candidate's own values.
    preset = dict(packet["presets"][NAME], model=case.profile["model"])
    enrollment = dict(packet["enrollments"][NAME],
                      secretFile=str(home / ".config/chaldea/authentik" / (NAME + ".app-password")))
    profile = dict(packet["profiles"][NAME], **{k: case.profile[k] for k in (
        "native", "host", "catalog", "elf_machine", "model", "home", "tmpdir", "cwd")})
    ceiling = dict(packet["ceilings"][0])
    variables["chaldea_client_session_ceilings"] = variables["chaldea_client_session_ceilings"] + [ceiling]
    variables["chaldea_client_session_presets"] = variables["chaldea_client_session_presets"] | {NAME: preset}
    variables["chaldea_client_session_enrollments"] = (
        variables["chaldea_client_session_enrollments"] | {NAME: enrollment})
    variables["chaldea_client_session_profiles"] = {NAME: profile}
    directory = Path(case.extra["chaldea_client_session_policy_path"]).parent / NAME
    helper = case.helper.replace(f"--preset {PRESET} --audience jocasta", f"--preset {NAME} --audience ov")
    assert helper != case.helper

    ok(run(case, check=True))
    assert not directory.exists() and not case.config.exists()
    ok(run(case))
    disabled = {"enabled": False, "command": "/usr/bin/false"}
    assert tomllib.loads(case.config.read_text()) == {"mcp_servers": {
        **{name: disabled for name in DISABLED},
        "ov_tooling": {"url": OV_URL, "http_headers_helper": helper, "enabled_tools": ["memory_stat"]}}}
    assert json.loads((directory / "mcp.json").read_text()) == {"mcpServers": {"ov_tooling": {
        "type": "http", "url": OV_URL, "headersHelper": helper}}}
    assert sorted(p.name for p in directory.iterdir()) == [
        "codex", "codex-code-mode-host", "exec", "mcp.json", "models.json"]
    # The FIFO stand-in for a login was never opened, and nothing else was added.
    assert sorted(p.name for p in (case.profile_home / ".codex").iterdir()) == ["auth.json", "config.toml"]
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    case.directory = directory
    launched = launch(case)
    assert launched.returncode == 0, launched.stderr
    assert launched.stdout.rstrip("\n").endswith("app-server --strict-config")
