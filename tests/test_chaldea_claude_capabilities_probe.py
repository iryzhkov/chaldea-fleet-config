"""Stock health initialization is a separate, explicitly opted-in no-tool protocol."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

from jinja2 import Environment
import pytest

from test_chaldea_client import ROOT
from test_chaldea_session_profiles import ok, run
from test_chaldea_session_profiles_claude import (
    CLAUDE, DENY, POLICY, claude_layout, corrected, launch, refused, t3_args,
)

# Captured from SDK0.3.276 running the exact upstream81493ef options builder.
# Diagnostic source3e1bc0f2 / agent-a36ef5ca9; no native/credentials/model used.
HEAD = ["--output-format", "stream-json", "--verbose", "--input-format", "stream-json",
        "--setting-sources=user,project,local"]
TAIL = ["--permission-mode", "default", "--no-session-persistence",
        "--settings", '{"disableAllHooks":true}']
PROBES = [HEAD + ["--strict-mcp-config"] + TAIL, HEAD + TAIL]
TEMPLATE = ROOT / "roles/chaldea_client/templates/claude-profile-exec.py.j2"


@pytest.mark.parametrize("trim", [False, True])
@pytest.mark.parametrize("selected", [None, False])
def test_default_launcher_bytes_equal_pre_probe_template(trim, selected):
    original = ROOT / "tests/fixtures/claude-profile-exec-before-probe.py.j2"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == (
        "dda1d8ec56a34627926455c9b8ee424aff685a49bdce330a9d0637fa33bf1e7e")
    env = Environment(trim_blocks=trim)
    env.filters.update(to_json=json.dumps, from_json=json.loads,
                       hash=lambda value, name: hashlib.new(name, value.encode()).hexdigest())
    profile = {"native": {"sha256": "1" * 64}, "elf_machine": 183, "cwd": "/fixture/reporter"}
    if selected is not None:
        profile["capabilities_probe"] = selected
    variables = {
        "chaldea_client_profile": {"value": profile},
        "chaldea_client_profile_dir": "/fixture/profile",
        "chaldea_client_profile_settings": json.dumps({"permissions": POLICY}),
        "chaldea_client_t3_home": "/fixture/.t3", "ansible_facts": {"user_uid": 1001},
    }
    assert env.from_string(TEMPLATE.read_text()).render(**variables) == (
        env.from_string(original.read_text()).render(**variables))


def test_probe_option_is_claude_only_and_strict_boolean(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    filter_file = ROOT / "roles/chaldea_client/filter_plugins/session_profiles.py"
    check = runpy.run_path(str(filter_file))["claude_profile"]
    for value in (True, False):
        check("fixture", case.claude | {"capabilities_probe": value})
    for value in (0, 1, None, "true", [], {}):
        with pytest.raises(Exception, match="capabilities_probe must be a boolean"):
            check("fixture", case.claude | {"capabilities_probe": value})


def test_opt_in_probe_is_empty_constrained_and_pinned(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    case.claude["capabilities_probe"] = True
    ok(run(case, check=True))
    assert not case.claude_dir.exists()
    ok(run(case))
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout
    module = runpy.run_path(str(case.claude_dir / "exec"))
    args = module["capabilities_probe_args"](PROBES[0])
    assert module["capabilities_probe_args"](PROBES[1]) == args
    assert args[args.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert args[args.index("--setting-sources") + 1] == ""
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--disallowed-tools") + 1] == "mcp__*"
    settings = json.loads(args[args.index("--settings") + 1])
    assert settings == {"disableAllHooks": True,
                        "permissions": {"allow": [], "deny": ["mcp__*", *DENY]}}
    assert case.helper not in " ".join(args) and case.mcp not in args
    assert "--restricted" in args and "--strict-mcp-config" in args
    # The source binary is echo. Actual descriptor exec proves the emitted argv
    # and fixed cwd even when T3's health check originated outside reporter cwd.
    for probe in PROBES:
        result = launch(case, probe, cwd=case.home)
        assert result.returncode == 0, result.stderr
        assert result.stdout == " ".join(args) + "\n"
    # Ordinary conversation behavior and all its argv constraints stay exact.
    normal = launch(case, t3_args(case))
    assert normal.returncode == 0 and normal.stdout == " ".join(corrected(case)) + "\n"
    mutations = [
        [], ["auth", "status"], PROBES[0] + ["--model", "other"],
        PROBES[0] + ["--tools", "Bash"], PROBES[0] + ["--mcp-config", case.mcp],
        PROBES[0] + ["--restricted"], PROBES[0] + ["--no-session-persistence"],
        [*PROBES[0][:-1], '{"disableAllHooks":false}'],
        [*PROBES[0][:-1], '{"disableAllHooks":true,"hooks":{}}'],
        [*PROBES[0][:-1], '{"disableAllHooks":true,"disableAllHooks":true}'],
        [x if x != "--setting-sources=user,project,local" else "--setting-sources=" for x in PROBES[0]],
        PROBES[0][:-2], list(reversed(PROBES[0])),
        t3_args(case) + ["--no-session-persistence"],
    ]
    for bad in mutations:
        refused(launch(case, bad))
    # Both policy and native pin checks apply to the health path too.
    for target in (case.claude_dir / "claude-settings.json", case.claude_dir / "claude"):
        old = target.read_bytes()
        target.write_bytes(old[:-1] + bytes([old[-1] ^ 1]))
        refused(launch(case, PROBES[0]))
        target.write_bytes(old)
    captured = []

    class Executed(BaseException):
        pass

    def execve(fd, argv, environment):
        captured.append((os.fstat(fd).st_ino, argv, environment))
        os.close(fd)
        raise Executed()

    monkeypatch.chdir(case.home)
    monkeypatch.setattr(sys, "argv", ["exec", *PROBES[0]])
    with patch.dict(os.environ, ENABLE_CLAUDEAI_MCP_SERVERS="true", FORCE_CODE_TERMINAL="caller"), (
        patch.object(os, "execve", side_effect=execve)
    ):
        with pytest.raises(Executed):
            module["main"]()
    inode, emitted, environment = captured[0]
    assert inode == (case.claude_dir / "claude").stat().st_ino
    assert emitted == [str(case.claude_dir / "claude"), *args]
    assert Path.cwd() == case.reporter
    assert environment["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false"
    assert environment["CLAUDE_CODE_AUTO_CONNECT_IDE"] == "0"
    assert environment["CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL"] == "1"
    assert "FORCE_CODE_TERMINAL" not in environment
    # Guarded cleanup is the existing inverse, including for an opt-in profile.
    variables = case.variables | {"chaldea_client_session_profiles": {},
                                  "chaldea_client_session_profiles_absent": [{"name": CLAUDE, "driver": "claude"}]}
    ok(run(case, entry="session-profiles-absent", variables=variables))
    assert not case.claude_dir.exists() and case.claude_native.exists()


def test_no_opt_in_still_refuses_stock_probe(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    ok(run(case))
    for probe in PROBES:
        refused(launch(case, probe))
