"""Fixed Claude provider profiles from the client role, applied only in scratch trees.

Reuses the Codex profile layout and runner. The Claude native binary is a copy of
the job host's echo, so the rendered launcher can be executed for real and the
exact corrected argv observed. The Codex fixtures stay in place to show that a
Claude profile writes nothing in any home.
"""
import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from test_chaldea_session_policy import PRESET
from test_chaldea_session_profiles import FILTER, PROFILE, TOOLS, URL, layout, ok, pin, relink, run

CLAUDE = "claude-tooling-reporter"
DENY = ["mcp__t3-code__*", "mcp__t3_code__*", "Bash", "PowerShell", "Read", "Write", "Edit",
        "Glob", "Grep", "WebFetch", "WebSearch", "Agent"]
POLICY = {"allow": ["mcp__jocasta_projectA__" + tool for tool in TOOLS], "deny": DENY}
REFUSED = "FIXED_EXEC_REFUSED\n"


def claude_layout(tmp_path, monkeypatch, keep_codex=False):
    case = layout(tmp_path, monkeypatch)
    native = case.home / ".local/share/claude/versions/2.1.276"
    native.parent.mkdir(parents=True)
    native.write_bytes(Path("/usr/bin/echo").read_bytes())
    native.chmod(0o755)
    reporter = case.home / "reporter"
    reporter.mkdir()
    profile = {"driver": "claude", "native": pin(native),
               "elf_machine": int.from_bytes(native.read_bytes()[18:20], "little"),
               "cwd": str(reporter), "preset": PRESET, "audience": "jocasta",
               "server": "jocasta_projectA", "url": URL, "tools": list(TOOLS)}
    profiles = {CLAUDE: profile}
    if keep_codex:
        profiles[PROFILE] = case.profile
    case.variables["chaldea_client_session_profiles"] = profiles
    case.claude = profile
    case.claude_native = native
    case.reporter = reporter
    case.claude_dir = case.directory.parent / CLAUDE
    case.attachments = case.home / ".t3/userdata/attachments"
    case.mcp = str(case.claude_dir / "mcp.json")
    return case


def t3_args(case, settings=None, extra=()):
    """The admitted argv shape the stock T3 Claude provider passes."""
    settings = settings or {"permissions": {"deny": ["mcp__t3-code__*"]}, "fastMode": False, "effortLevel": "medium"}
    return ["--restricted", "--strict-mcp-config", "--mcp-config", case.mcp, "--setting-sources", "",
            "--settings", json.dumps(settings), "--tools", "default", "--tools", "",
            "--disallowed-tools", "mcp__t3-code__*,mcp__t3_code__*", "--permission-mode", "default",
            "--output-format", "stream-json", "--input-format", "stream-json", "--add-dir", str(case.reporter),
            *extra]


def corrected(case):
    merged = json.dumps({"permissions": POLICY, "fastMode": False, "effortLevel": "medium"},
                        separators=(",", ":"), ensure_ascii=True)
    return ["--restricted", "--strict-mcp-config", "--mcp-config", case.mcp, "--setting-sources", "",
            "--settings", merged, "--tools", "", "--disallowed-tools", "mcp__t3-code__*,mcp__t3_code__*",
            "--permission-mode", "default", "--output-format", "stream-json", "--input-format", "stream-json",
            "--add-dir", str(case.reporter)]


def launch(case, argv, cwd=None):
    return subprocess.run([str(case.claude_dir / "exec"), *argv], cwd=cwd or case.reporter,
                          env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=60)


def refused(result):
    assert (result.returncode, result.stderr, result.stdout) == (78, REFUSED, ""), result


def test_claude_check_real_second_and_actual_launch(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    ok(run(case, check=True))
    assert not (case.protected / "etc/chaldea").exists()
    real = run(case)
    ok(real)
    assert "changed=0" not in real.stdout
    assert sorted(p.name for p in case.claude_dir.iterdir()) == ["claude", "claude-settings.json", "exec", "mcp.json"]
    assert (case.claude_dir / "claude").read_bytes() == case.claude_native.read_bytes()
    for name, mode in (("claude", 0o755), ("claude-settings.json", 0o644), ("mcp.json", 0o644), ("exec", 0o755)):
        st = (case.claude_dir / name).lstat()
        assert (st.st_mode & 0o7777, st.st_uid, st.st_gid, st.st_nlink) == (mode, os.getuid(), os.getgid(), 1)
    assert json.loads((case.claude_dir / "claude-settings.json").read_text()) == {"permissions": POLICY}
    assert json.loads((case.claude_dir / "mcp.json").read_text()) == {"mcpServers": {"jocasta_projectA": {
        "type": "http", "url": URL, "headersHelper": case.helper}}}
    # No home write: the Codex fixture home holds only its untouched FIFO.
    assert sorted(p.name for p in (case.profile_home / ".codex").iterdir()) == ["auth.json"]
    assert not case.directory.exists()
    source = (case.claude_dir / "exec").read_text()
    for absent in ("RECEIPT", "Receipt", "fcntl", "STAGES", "fsync"):
        assert absent not in source
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    # Actual execution: the launcher FD-executes the pinned echo copy with the corrected argv.
    before = sorted(os.listdir(case.reporter)), sorted(os.listdir(case.claude_dir))
    for extra in ((), ("--allowedTools", "mcp__t3-code__*", "--add-dir", str(case.attachments))):
        launched = launch(case, t3_args(case, extra=extra))
        assert launched.returncode == 0, launched.stderr
        assert launched.stdout == " ".join(corrected(case)) + "\n"
    assert (sorted(os.listdir(case.reporter)), sorted(os.listdir(case.claude_dir))) == before
    # Descriptor identity and inherited environment, observed in process.
    launcher = runpy.run_path(str(case.claude_dir / "exec"))
    captured = []

    class Executed(BaseException):
        pass

    def execve(fd, args, env):
        captured.append((os.fstat(fd).st_ino, args, env))
        raise Executed()
    monkeypatch.chdir(case.reporter)
    with patch.object(os, "execve", side_effect=execve):
        for argv in (t3_args(case), ["--version"]):
            monkeypatch.setattr(sys, "argv", ["exec", *argv])
            with pytest.raises(Executed):
                launcher["main"]()
    native = str(case.claude_dir / "claude")
    inode = (case.claude_dir / "claude").stat().st_ino
    assert captured == [(inode, [native, *corrected(case)], os.environ), (inode, [native, "--version"], os.environ)]


def argv_case(change):
    return lambda case: change(t3_args(case), case)


def replaced(args, flag, value):
    args[args.index(flag) + 1] = value
    return args


ARGV_REFUSALS = {
    "unknown flag": argv_case(lambda a, c: a + ["--dangerously-skip-permissions"]),
    "other mcp config": argv_case(lambda a, c: replaced(a, "--mcp-config", str(c.reporter / "mcp.json"))),
    "loose mcp": argv_case(lambda a, c: [x for x in a if x != "--strict-mcp-config"]),
    "unrestricted": argv_case(lambda a, c: [x for x in a if x != "--restricted"]),
    "bypass permissions": argv_case(lambda a, c: replaced(a, "--permission-mode", "bypassPermissions")),
    "setting sources": argv_case(lambda a, c: replaced(a, "--setting-sources", "user")),
    "settings hooks": argv_case(lambda a, c: replaced(a, "--settings", json.dumps({"hooks": {}}))),
    "settings duplicate key": argv_case(lambda a, c: replaced(a, "--settings", '{"fastMode":true,"fastMode":false}')),
    "other add dir": argv_case(lambda a, c: replaced(a, "--add-dir", str(c.home))),
    "allowed bash": argv_case(lambda a, c: a + ["--allowedTools", "Bash"]),
    "enabled tools": argv_case(lambda a, c: replaced(a, "--tools", "Bash")),
    "expansion": argv_case(lambda a, c: a + ["--model", "$(id)"]),
    "attachments without reporter": argv_case(lambda a, c: replaced(a, "--add-dir", str(c.attachments))),
}


def test_claude_launcher_refuses_argv_and_drift_before_native_exec(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    ok(run(case))
    assert launch(case, t3_args(case)).returncode == 0
    for name, make in ARGV_REFUSALS.items():
        result = launch(case, make(case))
        assert (result.returncode, result.stdout) == (78, ""), name
        refused(result)
    refused(launch(case, t3_args(case), cwd=case.home))
    native = case.claude_dir / "claude"
    for target, change in ((case.claude_dir / "claude-settings.json", lambda raw: raw + b" "),
                           (native, lambda raw: raw[:-1] + bytes([raw[-1] ^ 1]))):
        original = target.read_bytes()
        target.write_bytes(change(original))
        refused(launch(case, t3_args(case)))
        if target == native:
            refused(launch(case, ["--version"]))
        target.write_bytes(original)
    native.chmod(0o644)
    refused(launch(case, t3_args(case)))
    native.chmod(0o775)
    refused(launch(case, t3_args(case)))
    native.chmod(0o755)
    relink(native)
    refused(launch(case, t3_args(case)))
    native.unlink()
    native.with_name("claude.saved").rename(native)
    case.claude_dir.chmod(0o775)
    refused(launch(case, t3_args(case)))
    case.claude_dir.chmod(0o755)
    # Rebinding the settings hash still requires exactly the protected permissions.
    launcher = runpy.run_path(str(case.claude_dir / "exec"))
    settings = case.claude_dir / "claude-settings.json"
    original = settings.read_bytes()
    wider = json.dumps({"permissions": {"allow": POLICY["allow"] + ["Bash"], "deny": DENY}}).encode()
    settings.write_bytes(wider)
    monkeypatch.chdir(case.reporter)
    monkeypatch.setattr(sys, "argv", ["exec", *t3_args(case)])
    with patch.dict(launcher["main"].__globals__, POLICY_SHA256=hashlib.sha256(wider).hexdigest()), \
         patch.object(os, "execve", side_effect=AssertionError("must not exec")):
        with pytest.raises(ValueError):
            launcher["main"]()
    settings.write_bytes(original)
    launched = launch(case, t3_args(case))
    assert launched.returncode == 0 and launched.stdout == " ".join(corrected(case)) + "\n"


def mutate_claude(change):
    def apply(case):
        change(case.claude, case)
    return apply


def protected_link(case):
    case.claude_dir.mkdir(parents=True)
    (case.claude_dir / "exec").symlink_to(case.claude_native)


CLAUDE_REFUSALS = {
    "codex field": (mutate_claude(lambda p, c: p.update(home=str(c.profile_home))), FILTER),
    "missing cwd": (mutate_claude(lambda p, c: p.pop("cwd")), FILTER),
    "companion pin": (mutate_claude(lambda p, c: p.update(host=dict(p["native"]))), FILTER),
    "reserved server": (mutate_claude(lambda p, c: p.update(server="t3_code")), FILTER),
    "ungranted tool": (mutate_claude(lambda p, c: p.update(tools=TOOLS + ["put"])), FILTER),
    "url differs from enrollment": (mutate_claude(lambda p, c: p.update(url="https://other.example.test/mcp")), FILTER),
    "native over launcher limit": (mutate_claude(lambda p, c: p["native"].update(size=400000001)), FILTER),
    "relative cwd": (mutate_claude(lambda p, c: p.update(cwd="reporter")), FILTER),
    "retired codex driver form": (lambda c: c.variables.update(chaldea_client_session_profiles_absent=[
        {"name": "old", "driver": "codex"}]), FILTER),
    "native hash": (mutate_claude(lambda p, c: p["native"].update(sha256="0" * 64)), "pinned size"),
    "native size": (mutate_claude(lambda p, c: p["native"].update(size=p["native"]["size"] - 1)), "pinned size"),
    "native link": (lambda c: relink(c.claude_native), "pinned size"),
    "writable native": (lambda c: c.claude_native.chmod(0o777), "pinned size"),
    "linked launcher target": (protected_link, "must be absent or owned"),
}


@pytest.mark.parametrize("name", sorted(CLAUDE_REFUSALS))
def test_claude_refused_before_any_profile_write(tmp_path, monkeypatch, name):
    case = claude_layout(tmp_path, monkeypatch)
    change, message = CLAUDE_REFUSALS[name]
    change(case)
    result = run(case)
    assert result.returncode != 0, result.stdout
    assert message in result.stdout, result.stdout[-12000:]
    assert not (case.claude_dir / "claude").exists()
    assert not (case.claude_dir / "claude-settings.json").exists()


def test_mixed_profiles_and_claude_inverse_leave_codex_alone(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch, keep_codex=True)
    ok(run(case))
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    codex = {p.name: p.read_bytes() for p in case.directory.iterdir()}
    config = case.config.read_bytes()
    variables = case.variables | {
        "chaldea_client_session_profiles": {PROFILE: case.profile},
        "chaldea_client_session_profiles_absent": [{"name": CLAUDE, "driver": "claude"}]}
    ok(run(case, entry="session-profiles-absent", check=True, variables=variables))
    assert (case.claude_dir / "exec").exists()
    ok(run(case, entry="session-profiles-absent", variables=variables))
    assert not case.claude_dir.exists() and case.claude_native.exists()
    assert {p.name: p.read_bytes() for p in case.directory.iterdir()} == codex
    assert case.config.read_bytes() == config
    again = run(case, entry="session-profiles-absent", variables=variables)
    ok(again)
    assert "changed=0" in again.stdout, again.stdout
    # Codex convergence is still unchanged after the Claude retirement.
    unchanged = run(case, variables=variables | {"chaldea_client_session_profiles_absent": []})
    ok(unchanged)
    assert "changed=0" in unchanged.stdout, unchanged.stdout


def test_claude_inverse_refuses_foreign_paths(tmp_path, monkeypatch):
    case = claude_layout(tmp_path, monkeypatch)
    ok(run(case))
    variables = case.variables | {"chaldea_client_session_profiles": {},
                                  "chaldea_client_session_profiles_absent": [{"name": CLAUDE, "driver": "claude"}]}
    relink(case.claude_dir / "claude-settings.json")
    result = run(case, entry="session-profiles-absent", variables=variables)
    assert result.returncode != 0 and "is not a role-owned profile path" in result.stdout, result.stdout[-8000:]
    assert all((case.claude_dir / n).exists() for n in ("exec", "claude", "mcp.json", "claude-settings.json.saved"))
