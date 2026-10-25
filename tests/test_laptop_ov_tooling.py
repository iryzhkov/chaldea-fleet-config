"""Laptop OV activation draft, checked against the real owning inventory.

The reviewed example remains the desired-value reference. These tests bind it
to the real third entry, preserve every original Jocasta value, reject widened
or shared variants and deliver the actual OV profile through the role in scratch.
The Jocasta inventory test renders and checks the complete protected policy.
No fixture reads a credential or touches a model login.
"""
import copy
import hashlib
import json
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
    """Replace only OV values for negative cases, retaining the real inventory."""
    values = activation()
    if packet is not None:
        values["chaldea_client_session_ceilings"][-1:] = copy.deepcopy(packet["ceilings"])
        for short in MAPS:
            values["chaldea_client_session_" + short][NAME] = copy.deepcopy(packet[short][NAME])
    return values


def validate(values):
    load("session_enrollment").chaldea_session_enrollments(
        values["chaldea_client_session_enrollments"], values["chaldea_client_session_presets"],
        values["chaldea_client_session_ceilings"], HOME)
    return validate_profiles(values)


def test_real_inventory_adds_exact_ov_entries_and_preserves_all_original_values():
    packet = candidate()
    assert set(packet) == {"ceilings", *MAPS}
    assert all(set(packet[short]) == {NAME} for short in MAPS)
    laptop = inventory_vars("laptop")
    after = activation()
    assert after["chaldea_client_session_ceilings"][-1:] == packet["ceilings"]
    assert len(after["chaldea_client_session_ceilings"]) == 2
    before = copy.deepcopy(after)
    before["chaldea_client_session_ceilings"].pop()
    for short in MAPS:
        key = "chaldea_client_session_" + short
        assert list(after[key]) == ["jocasta-tooling-claude", CODEX, NAME]
        assert after[key][NAME] == packet[short][NAME]
        assert laptop[key] == after[key]
        before[key].pop(NAME)
    assert laptop["chaldea_client_session_ceilings"] == after["chaldea_client_session_ceilings"]
    # Canonical full owning hostfile at base 15f1950, measured on agent-a before
    # editing. Removing only the four OV additions must recover EVERY old value,
    # including prompts, native pins, HOME/cwd, grants and ordinary timer settings.
    canonical = json.dumps(before, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == (
        "c810430f87db92769cecb239c1a7270df06dc8f001181b9329ebc3843ffa8e37")


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


def test_actual_role_delivers_the_ov_profile_with_its_closed_server(tmp_path, monkeypatch):
    from test_chaldea_session_profiles import PRESET, launch, layout, ok, run

    case = layout(tmp_path, monkeypatch)
    values = activation()
    packet = {"ceilings": values["chaldea_client_session_ceilings"][-1:]}
    packet.update({short: {NAME: values["chaldea_client_session_" + short][NAME]} for short in MAPS})
    home = case.home
    variables = case.variables
    # Binaries, model, home and paths are the scratch fixture's; the preset,
    # grant, enrollment, server, URL, tools and neutralized servers are the
    # actual inventory's own values.
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
