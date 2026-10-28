"""Fixed OpenCode provider profiles from the client role, applied only in scratch trees.

Reuses the Codex profile layout and runner. The pinned "native" is a copy of the
job host's bash, so the rendered launcher really FD-executes it: bash then runs
the scenario script named serve in the T3 server directory, which stands in for
`opencode serve`. The headers helper is a test-only fake placed at the profile's
Node path; it follows the provisional --context/--expect-* contract and issues
synthetic unsigned headers. Neither fake exists outside these scratch trees.
"""
import base64
import json
import os
import runpy
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from test_chaldea_session_policy import PRESET
from test_chaldea_session_profiles import FILTER, PROFILE, TOOLS, URL, layout, ok, pin, relink, run

OPENCODE = "opencode-tooling-reporter"
SERVER = "jocasta_projecta"
REFUSED = "OPENCODE_PROFILE_REFUSED\n"
PASSWORD = "synthetic-serve-password"
SERVE_ARGV = ["serve", "--hostname=127.0.0.1", "--port=4096"]
POLICIES = [
    {"action": "tool.use", "resource": "*", "effect": "deny"},
    {"action": "tool.use", "resource": SERVER + "_*", "effect": "allow"},
    {"action": "tool.use", "resource": "t3-code-*", "effect": "allow"},
    {"action": "integration.use", "resource": "mcp:*", "effect": "deny"},
    {"action": "integration.use", "resource": "mcp:" + SERVER, "effect": "allow"},
    {"action": "integration.use", "resource": "mcp:t3-code-*", "effect": "allow"}]

FAKE_HELPER = r'''#!/usr/bin/python3 -I
import base64, json, os, sys, time
state_path = os.environ["HOME"] + "/fake-helper/state.json"
with open(state_path) as handle:
    state = json.load(handle)
state["calls"].append(sys.argv[1:])
state.setdefault("pids", []).append(os.getpid())
step = state["steps"][min(len(state["calls"]), len(state["steps"])) - 1]
now = int(time.time())
exp = state["last_exp"] if step.get("same") else now + step.get("ttl", 28)
state["last_exp"] = exp
with open(state_path + ".tmp", "w") as handle:
    json.dump(state, handle)
os.replace(state_path + ".tmp", state_path)
time.sleep(step.get("sleep", 0))
if "refuse" in step:
    sys.stderr.write(step["refuse"] + "\n")
    sys.exit(1)
claims = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
context = {"sessionId": step.get("session", "sess-1"), "runId": step.get("run", "run-1"),
           "deadline": state["deadline"], "tokenExpiresAt": exp}
header = "Bearer eyJhbGciOiJub25lIn0." + claims + ".c3ludGhldGlj" + str(len(state["calls"]))
print(json.dumps({"headers": {"Authorization": header}, "context": context}))
'''

FAKE_SERVE = r'''import json, os, signal, subprocess, sys, time
base = os.getcwd()
with open(base + "/scenario.json") as handle:
    scenario = json.load(handle)
config = os.environ["OPENCODE_CONFIG_DIR"]
record = {"argv": sys.argv[1:], "env": dict(os.environ), "pid": os.getpid(), "pgid": os.getpgrp(),
          "dir_mode": os.stat(config).st_mode & 0o777, "listing": sorted(os.listdir(config)),
          "config": open(config + "/opencode.json").read(), "seen": []}
if scenario.get("grandchild"):
    script = ("import signal,time; from pathlib import Path; "
              + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if scenario.get("grandchild_ignore_term") else "")
              + "Path('grandchild-ready').write_text('ready'); time.sleep(120)")
    record["grandchild"] = subprocess.Popen(["/usr/bin/python3", "-c", script],
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL).pid
    while not os.path.exists("grandchild-ready"):
        time.sleep(0.01)
def save():
    with open(base + "/serve-record.tmp", "w") as handle:
        json.dump(record, handle)
    os.replace(base + "/serve-record.tmp", base + "/serve-record.json")
def term(*_):
    record["terminated"] = True
    save()
    sys.exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN if scenario.get("ignore_term") else term)
save()
print("opencode server listening on http://127.0.0.1:4096", flush=True)
end = time.time() + scenario.get("lifetime", 60)
while time.time() < end:
    try:
        path = config + "/jocasta.authorization"
        value, meta = open(path).read(), os.stat(path)
    except FileNotFoundError:
        value = None
    if value and (not record["seen"] or record["seen"][-1]["value"] != value):
        record["seen"].append({"value": value, "ino": meta.st_ino, "mode": meta.st_mode & 0o777})
        save()
    time.sleep(0.05)
save()
sys.exit(scenario.get("exit", 0))
'''


def opencode_layout(tmp_path, monkeypatch, keep_codex=False):
    case = layout(tmp_path, monkeypatch)
    native = case.home / ".local/share/chaldea/provider-assets/opencode/2.1.3/opencode"
    native.parent.mkdir(parents=True)
    native.write_bytes(Path("/bin/bash").read_bytes())
    native.chmod(0o755)
    state = case.home / ".local/state/chaldea/profiles" / OPENCODE
    home, tmpdir = state / "home", state / "run"
    for path in (home, tmpdir):
        path.mkdir(parents=True)
        path.chmod(0o700)
    server = case.home / "t3-server"
    server.mkdir()
    (server / "serve").write_text('exec /usr/bin/python3 -I "$PWD/fake_serve.py" "$@"\n')
    (server / "fake_serve.py").write_text(FAKE_SERVE)
    (server / "scenario.json").write_text("{}")
    node = Path(case.helper.split()[0])
    node.parent.mkdir(parents=True)
    node.write_text(FAKE_HELPER)
    node.chmod(0o755)
    (case.home / "fake-helper").mkdir()
    profile = {"driver": "opencode", "native": pin(native),
               "elf_machine": int.from_bytes(native.read_bytes()[18:20], "little"),
               "home": str(home), "tmpdir": str(tmpdir), "cwd": str(server), "preset": PRESET,
               "audience": "jocasta", "server": SERVER, "url": URL, "tools": list(TOOLS)}
    profiles = {OPENCODE: profile}
    if keep_codex:
        profiles[PROFILE] = case.profile
    case.variables["chaldea_client_session_profiles"] = profiles
    case.opencode = profile
    case.opencode_native = native
    case.opencode_home, case.runtime, case.server = home, tmpdir, server
    case.opencode_dir = case.directory.parent / OPENCODE
    case.helper_argv = case.helper.split()
    return case


def helper_steps(case, steps, deadline=None):
    deadline = deadline or int(time.time()) + 1800
    (case.home / "fake-helper/state.json").write_text(json.dumps(
        {"steps": steps, "calls": [], "deadline": deadline, "last_exp": 0}))
    return deadline


def helper_calls(case):
    return json.loads((case.home / "fake-helper/state.json").read_text())["calls"]


def scenario(case, **values):
    (case.server / "scenario.json").write_text(json.dumps(values))


def serve_record(case):
    return json.loads((case.server / "serve-record.json").read_text())


def start(case, argv=SERVE_ARGV, cwd=None):
    """Start the launcher like T3: its own process group, T3 variables in the environment."""
    env = {"PATH": "/usr/bin:/bin", "OPENCODE_PASSWORD": PASSWORD, "OPENCODE_CONFIG_CONTENT": '{"policies":[]}',
           "OPENCODE_CONFIG": "/elsewhere.json", "XDG_CONFIG_HOME": "/elsewhere", "HOME": str(case.home)}
    return subprocess.Popen([str(case.opencode_dir / "exec"), *argv], cwd=cwd or case.server, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)


def finish(process, timeout=40):
    stdout, stderr = process.communicate(timeout=timeout)
    return process.returncode, stdout, stderr


def gone(pid):
    """No live process: absent, or only a zombie awaiting its new parent."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return True


def wait_for(condition, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def expected_env(case, launch_dir):
    home = str(case.opencode_home)
    return {"HOME": home, "XDG_CONFIG_HOME": home + "/.config", "XDG_DATA_HOME": home + "/.local/share",
            "XDG_STATE_HOME": home + "/.local/state", "XDG_CACHE_HOME": home + "/.cache",
            "TMPDIR": launch_dir + "/tmp", "PATH": "/usr/bin:/bin", "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
            "OPENCODE_CONFIG_PROJECT_DISABLE": "1", "OPENCODE_DISABLE_CLAUDE_CODE": "1",
            "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1", "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_DISABLE_MODELS_FETCH": "1", "OPENCODE_CONFIG_DIR": launch_dir + "/config",
            "OPENCODE_PASSWORD": PASSWORD}


def bound_argv(case, extra):
    return [*case.helper_argv[1:-2], "--context", *extra, *case.helper_argv[-2:]]


def test_opencode_check_real_second_and_public_files(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case, check=True))
    assert not (case.protected / "etc/chaldea").exists()
    real = run(case)
    ok(real)
    assert "changed=0" not in real.stdout
    assert sorted(p.name for p in case.opencode_dir.iterdir()) == ["exec", "opencode", "opencode.json"]
    assert (case.opencode_dir / "opencode").read_bytes() == case.opencode_native.read_bytes()
    for name, mode in (("opencode", 0o755), ("opencode.json", 0o644), ("exec", 0o755)):
        st = (case.opencode_dir / name).lstat()
        assert (st.st_mode & 0o7777, st.st_uid, st.st_gid, st.st_nlink) == (mode, os.getuid(), os.getgid(), 1)
    assert json.loads((case.opencode_dir / "opencode.json").read_text()) == {
        "$schema": "https://opencode.ai/config.json", "policies": POLICIES,
        "mcp": {SERVER: {"type": "remote", "url": URL, "oauth": False, "enabled": True,
                         "headers": {"Authorization": "{file:jocasta.authorization}"}}}}
    # Nothing written in the operator-provisioned home or runtime directory.
    assert list(case.opencode_home.iterdir()) == [] and list(case.runtime.iterdir()) == []
    launcher = runpy.run_path(str(case.opencode_dir / "exec"))
    assert launcher["HELPER"] == case.helper_argv
    assert launcher["HELPER_ENV"] == {"HOME": str(case.home), "PATH": "/usr/bin:/bin"}
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    version = subprocess.run([str(case.opencode_dir / "exec"), "--version"], cwd=case.home, env={"PATH": "/usr/bin:/bin"},
                             capture_output=True, text=True, timeout=30)
    assert version.returncode == 0 and "bash" in version.stdout, version
    # The probe ran through a private launch directory that is gone again, with no header.
    assert helper_calls_absent(case) and list(case.runtime.iterdir()) == []


def helper_calls_absent(case):
    return not (case.home / "fake-helper/state.json").exists()


def test_launch_renews_bound_header_and_ends_on_session_swap(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    scenario(case, grandchild=True)
    deadline = helper_steps(case, [{}, {}, {"session": "sess-2"}])
    process = start(case)
    code, stdout, stderr = finish(process)
    assert (code, stderr) == (78, "OPENCODE_PROFILE_ENDED session_changed\n"), (stdout, stderr)
    assert stdout == "opencode server listening on http://127.0.0.1:4096\n"
    record = serve_record(case)
    launch_dir = str(Path(record["env"]["OPENCODE_CONFIG_DIR"]).parent)
    assert Path(launch_dir).parent == case.runtime and Path(launch_dir).name.startswith("opencode-")
    # bash and Python in the fake serve add PWD, SHLVL and LC_CTYPE themselves.
    added = {"PWD", "SHLVL", "LC_CTYPE"}
    assert {k: v for k, v in record["env"].items() if k not in added} == expected_env(case, launch_dir)
    assert record["argv"] == SERVE_ARGV[1:]
    # The serve child stayed in the launcher's (T3-owned) process group.
    assert record["pgid"] == process.pid and record["dir_mode"] == 0o700
    assert record["listing"] == ["jocasta.authorization", "opencode.json"]
    assert record["config"] == (case.opencode_dir / "opencode.json").read_text()
    seen = record["seen"]
    assert len(seen) == 2 and seen[0]["value"] != seen[1]["value"] and seen[0]["ino"] != seen[1]["ino"]
    assert all(entry["mode"] == 0o600 and entry["value"].startswith("Bearer ") for entry in seen)
    expect = ["--expect-session", "sess-1", "--expect-run", "run-1", "--expect-deadline", str(deadline)]
    assert helper_calls(case) == [bound_argv(case, []), bound_argv(case, expect), bound_argv(case, expect)]
    assert record.get("terminated") and gone(record["pid"]) and gone(record["grandchild"])
    assert list(case.runtime.iterdir()) == []
    for entry in seen:
        assert entry["value"] not in stdout + stderr


@pytest.mark.parametrize("steps, reason, calls", [
    ([{}, {"refuse": "session_mismatch"}], "session_mismatch", 2),
    ([{}, {"same": True}], "renewal_insufficient", 2),
    ([{}, {"run": "run-2"}], "session_changed", 2),
    ([{}, {"refuse": "Bearer leaked"}], "helper_refused", 2),
    ([{"refuse": "session_inactive"}], "session_inactive", 1),
    ([{"ttl": 20}], "renewal_insufficient", 1),
])
def test_first_refusal_or_insufficient_renewal_ends_the_launch(tmp_path, monkeypatch, steps, reason, calls):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    helper_steps(case, steps)
    code, stdout, stderr = finish(start(case))
    assert (code, stderr) == (78, f"OPENCODE_PROFILE_ENDED {reason}\n"), (stdout, stderr)
    assert len(helper_calls(case)) == calls
    assert list(case.runtime.iterdir()) == []
    if calls == 1:
        # Bootstrap refusal: no serve child ever started.
        assert stdout == "" and not (case.server / "serve-record.json").exists()
    else:
        assert gone(serve_record(case)["pid"])


def test_helper_timeout_ends_the_launch_and_kills_the_helper(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    helper_steps(case, [{}, {"sleep": 60}])
    started = time.monotonic()
    code, _, stderr = finish(start(case))
    assert (code, stderr) == (78, "OPENCODE_PROFILE_ENDED helper_timeout\n")
    assert time.monotonic() - started < 25
    assert gone(serve_record(case)["pid"]) and list(case.runtime.iterdir()) == []
    pids = json.loads((case.home / "fake-helper/state.json").read_text())["pids"]
    assert len(pids) == 2 and all(gone(pid) for pid in pids)


def test_t3_group_signal_and_child_exit_are_propagated(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    scenario(case, grandchild=True)
    helper_steps(case, [{}])
    process = start(case)
    assert wait_for(lambda: (case.server / "serve-record.json").exists())
    # T3's own termination: SIGTERM to the launcher's process group.
    os.killpg(process.pid, signal.SIGTERM)
    code, _, stderr = finish(process)
    assert (code, stderr) == (128 + signal.SIGTERM, "")
    record = serve_record(case)
    assert gone(record["pid"]) and wait_for(lambda: gone(record["grandchild"]))
    assert list(case.runtime.iterdir()) == []
    (case.server / "serve-record.json").unlink()
    scenario(case, lifetime=0.5, exit=7)
    helper_steps(case, [{}])
    code, _, stderr = finish(start(case))
    assert (code, stderr) == (7, "")
    assert len(helper_calls(case)) == 1 and list(case.runtime.iterdir()) == []


def test_child_ignoring_term_is_killed_after_bounded_grace(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    scenario(case, ignore_term=True)
    helper_steps(case, [{}, {"refuse": "session_mismatch"}])
    code, _, stderr = finish(start(case))
    assert (code, stderr) == (78, "OPENCODE_PROFILE_ENDED session_mismatch\n")
    assert gone(serve_record(case)["pid"]) and list(case.runtime.iterdir()) == []



@pytest.mark.parametrize("natural_exit", [True, False])
def test_owned_group_reaps_lingering_and_term_ignoring_grandchildren(tmp_path, monkeypatch, natural_exit):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    scenario(case, grandchild=True, grandchild_ignore_term=True,
             lifetime=0.5 if natural_exit else 60, exit=7)
    helper_steps(case, [{}] if natural_exit else [{}, {"refuse": "session_mismatch"}])
    process = start(case)
    try:
        code, _, stderr = finish(process, timeout=15)
        assert (code, stderr) == ((7, "") if natural_exit else
                                  (78, "OPENCODE_PROFILE_ENDED session_mismatch\n"))
        record = serve_record(case)
        assert gone(record["pid"]) and gone(record["grandchild"])
        assert list(case.runtime.iterdir()) == []
    finally:
        # This is a synthetic job-only process group, including on the red baseline.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=10)


@pytest.mark.parametrize("advance, expires, deadline, reason", [
    (11, 1300, 5000, "helper_timeout"),
    (6, 1005, 5000, "renewal_missed"),
    (6, 1300, 1005, "deadline"),
])
def test_helper_completion_after_suspend_is_refused(tmp_path, monkeypatch, advance, expires, deadline, reason):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    launcher = in_process(case)
    clock = FakeClock(1000.0)
    launch = launcher["Launch"](clock)
    launch.identity, launch.expires = ("sess-1", "run-1", deadline), expires
    launch.wait = lambda timeout: setattr(clock, "value", clock.value + advance)

    def completed_helper(target, argv, env, stdio):
        context = {"sessionId": "sess-1", "runId": "run-1",
                   "deadline": deadline, "tokenExpiresAt": min(deadline, 1400)}
        os.write(stdio[1], helper_line(context))
        return 424242

    with patch.dict(launcher["Launch"].helper.__globals__,
                    spawn=completed_helper, boottime=lambda: clock.value), \
         patch.object(os, "waitpid", lambda pid, flags: (pid, 0)):
        with pytest.raises(launcher["Refused"], match=reason):
            launch.helper()
    assert launch.expires == expires


def test_supervise_never_publishes_across_the_old_header_stop_margin(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    launcher = in_process(case)
    clock = FakeClock(1275.0)
    launch = supervised(launcher, clock, 1300, 5000, lambda t: t, [])

    def suspended_helper():
        clock.value += 30
        return "Bearer a.b.c", launch.identity, 1600

    launch.helper = suspended_helper
    with pytest.raises(launcher["Refused"], match="renewal_missed"):
        launch.supervise()
    assert launch.published == [] and launch.expires == 1300


def test_uncatchable_launcher_kill_takes_the_child_with_it(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    helper_steps(case, [{}])
    process = start(case)
    assert wait_for(lambda: (case.server / "serve-record.json").exists())
    os.kill(process.pid, signal.SIGKILL)
    process.communicate(timeout=10)
    record = serve_record(case)
    assert wait_for(lambda: gone(record["pid"]))
    # No cleanup handler runs after SIGKILL: the private directory and its short-lived
    # header remain until the operator removes them; the header expires on its own.
    leftover = Path(record["env"]["OPENCODE_CONFIG_DIR"])
    assert sorted(p.name for p in leftover.iterdir()) == ["jocasta.authorization", "opencode.json"]


def test_policy_copy_tamper_ends_the_launch_at_the_next_renewal(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    helper_steps(case, [{}, {}])
    process = start(case)
    assert wait_for(lambda: (case.server / "serve-record.json").exists())
    copy = Path(serve_record(case)["env"]["OPENCODE_CONFIG_DIR"]) / "opencode.json"
    copy.chmod(0o600)
    copy.write_text('{"policies": []}')
    copy.chmod(0o400)
    code, _, stderr = finish(process)
    assert (code, stderr) == (78, "OPENCODE_PROFILE_ENDED tampered\n")
    assert len(helper_calls(case)) == 1


def argv_refusal(argv):
    return lambda case: start(case, argv=argv)


def drift(change):
    def apply(case):
        change(case)
        return start(case)
    return apply


LAUNCH_REFUSALS = {
    "no argv": argv_refusal([]),
    "other hostname": argv_refusal(["serve", "--hostname=0.0.0.0", "--port=4096"]),
    "port zero": argv_refusal(["serve", "--hostname=127.0.0.1", "--port=0"]),
    "port text": argv_refusal(["serve", "--hostname=127.0.0.1", "--port=4096x"]),
    "extra flag": argv_refusal([*SERVE_ARGV, "--print-logs"]),
    "cli inventory": argv_refusal(["models", "--verbose"]),
    "acp": argv_refusal(["acp"]),
    "other cwd": lambda case: start(case, cwd=case.home),
    "config drift": drift(lambda c: (c.opencode_dir / "opencode.json").write_text("{}")),
    "native drift": drift(lambda c: (c.opencode_dir / "opencode").write_bytes(
        (raw := (c.opencode_dir / "opencode").read_bytes())[:-1] + bytes([raw[-1] ^ 1]))),
    "native link": drift(lambda c: relink(c.opencode_dir / "opencode")),
    "shared home": drift(lambda c: c.opencode_home.chmod(0o750)),
    "missing runtime": drift(lambda c: c.runtime.rmdir()),
}


@pytest.mark.parametrize("name", sorted(LAUNCH_REFUSALS))
def test_launcher_refuses_before_any_helper_call(tmp_path, monkeypatch, name):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    helper_steps(case, [{}])
    code, stdout, stderr = finish(LAUNCH_REFUSALS[name](case))
    assert (code, stdout, stderr) == (78, "", REFUSED)
    assert helper_calls(case) == [] and not (case.server / "serve-record.json").exists()


def in_process(case):
    return runpy.run_path(str(case.opencode_dir / "exec"))


class FakeClock:
    def __init__(self, now):
        self.value = now

    def now(self):
        return self.value


def supervised(launcher, clock, expires, deadline, waits, renewals):
    """A launch whose waits advance the fake clock and whose helper returns the given renewals."""
    launch = launcher["Launch"](clock)
    launch.identity, launch.expires = ("sess-1", "run-1", deadline), expires
    launch.published, launch.timeouts = [], []

    def wait(timeout):
        launch.timeouts.append(timeout)
        clock.value += waits(timeout)

    def helper():
        result = renewals.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    launch.wait, launch.helper, launch.intact = wait, helper, lambda: None
    launch.publish = launch.published.append
    return launch


def test_expiry_aware_schedule_suspend_and_deadline(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    launcher = in_process(case)
    refused = launcher["Refused"]
    identity = ("sess-1", "run-1", 5000)
    # Renewal happens 25 seconds before expiry, inside the helper's 30-second cache
    # threshold, with bounded waits; then the first refusal ends supervision.
    clock = FakeClock(1000.0)
    launch = supervised(launcher, clock, 1300, 5000, lambda t: t,
                        [("Bearer a.b.c", identity, 1575), refused("session_mismatch")])
    with pytest.raises(refused, match="session_mismatch"):
        launch.supervise()
    assert launch.published == ["Bearer a.b.c"] and launch.expires == 1575
    assert clock.value == 1550 and max(launch.timeouts) <= launcher["WAKE_CAP"]
    # A suspend past the stop margin ends access without asking the helper again.
    clock = FakeClock(1000.0)
    launch = supervised(launcher, clock, 1300, 5000, lambda t: 296, [])
    with pytest.raises(refused, match="renewal_missed"):
        launch.supervise()
    assert launch.published == []
    # The original admission deadline ends the launch even with a valid header.
    clock = FakeClock(1000.0)
    launch = supervised(launcher, clock, 1300, 1100, lambda t: t, [])
    with pytest.raises(refused, match="deadline"):
        launch.supervise()
    assert clock.value == 1100
    # A child exit ends supervision without a helper call.
    clock = FakeClock(1000.0)
    launch = supervised(launcher, clock, 1300, 5000, lambda t: t, [])
    launch.wait = lambda timeout: setattr(launch, "status", 0)
    assert launch.supervise() is None and launch.published == []


def test_clock_never_runs_behind_wall_or_boot_time(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    launcher = in_process(case)
    wall, boot = [1000.0], [50.0]
    with patch.dict(launcher["Clock"].now.__globals__, boottime=lambda: boot[0]), \
         patch.object(time, "time", lambda: wall[0]):
        clock = launcher["Clock"]()
        wall[0], boot[0] = 900.0, 60.0
        assert clock.now() == 1010.0  # wall clock set back: elapsed boot time still counts
        wall[0], boot[0] = 2000.0, 61.0
        assert clock.now() == 2000.0  # wall clock jumped ahead: the earlier expiry wins
        wall[0], boot[0] = 1000.0, 400.0
        assert clock.now() == 1350.0  # suspend: boot time includes it


def helper_line(context, header=None, extra=None):
    claims = base64.urlsafe_b64encode(json.dumps({"exp": context["tokenExpiresAt"]}).encode()).rstrip(b"=").decode()
    value = {"headers": {"Authorization": header or "Bearer h." + claims + ".s"}, "context": context}
    value.update(extra or {})
    return (json.dumps(value) + "\n").encode()


def test_helper_output_is_exact_and_bound(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    launcher = in_process(case)
    parsed, refused = launcher["parsed"], launcher["Refused"]
    good = {"sessionId": "sess-1", "runId": "run-1", "deadline": 5000, "tokenExpiresAt": 1300}
    header, identity, expires = parsed(helper_line(good), None)
    assert (identity, expires) == (("sess-1", "run-1", 5000), 1300) and header.startswith("Bearer h.")
    assert parsed(helper_line(good), identity)[1] == identity
    bad = {
        "other session": (helper_line(good | {"sessionId": "sess-2"}), identity),
        "other deadline": (helper_line(good | {"deadline": 5001}), identity),
        "outlives deadline": (helper_line(good | {"tokenExpiresAt": 5001}), None),
        "extra key": (helper_line(good, extra={"note": 1}), None),
        "extra context": (helper_line(good | {"preset": "p"}), None),
        "option id": (helper_line(good | {"runId": "--config"}), None),
        "float expiry": (helper_line(good | {"tokenExpiresAt": 1300.5}), None),
        "exp mismatch": (helper_line(good, header="Bearer h." + base64.urlsafe_b64encode(b'{"exp":1}').decode().rstrip("=")
                                     + ".s"), None),
        "not bearer": (helper_line(good, header="Basic abc"), None),
        "two lines": (helper_line(good) * 2, None),
        "duplicate key": (b'{"headers":{},"headers":{}}\n', None),
        "no newline": (helper_line(good)[:-1], None),
    }
    for name, (raw, bound) in bad.items():
        with pytest.raises(refused):
            parsed(raw, bound)
        assert name


def mutate(change):
    def apply(case):
        change(case.opencode, case)
    return apply


OPENCODE_REFUSALS = {
    "claude form": (mutate(lambda p, c: p.pop("home")), FILTER),
    "codex field": (mutate(lambda p, c: p.update(model="x")), FILTER),
    "reserved server": (mutate(lambda p, c: p.update(server="t3_code")), FILTER),
    "dash server": (mutate(lambda p, c: p.update(server="jocasta-x")), FILTER),
    "home is fleet home": (mutate(lambda p, c: p.update(home=str(c.home))), FILTER),
    "tmpdir is home": (mutate(lambda p, c: p.update(tmpdir=p["home"])), FILTER),
    "home outside fleet": (mutate(lambda p, c: p.update(home="/var/opencode")), FILTER),
    "cwd outside fleet": (mutate(lambda p, c: p.update(cwd="/srv")), FILTER),
    "ungranted tool": (mutate(lambda p, c: p.update(tools=TOOLS + ["put"])), FILTER),
    "url differs": (mutate(lambda p, c: p.update(url="https://other.example.test/mcp")), FILTER),
    "native over limit": (mutate(lambda p, c: p["native"].update(size=400000001)), FILTER),
    "ollama endpoint not approved": (mutate(lambda p, c: p.update(ollama_base_url="http://192.0.2.1:11434/v1")),
                                     FILTER),
    "ollama endpoint over https": (mutate(lambda p, c: p.update(ollama_base_url="https://127.0.0.1:11434/v1")),
                                   FILTER),
    "ollama endpoint without its model": (mutate(lambda p, c: p.update(ollama_base_url="http://127.0.0.1:11434/v1")),
                                          FILTER),
    "ollama model without an endpoint": (lambda c: c.variables["chaldea_client_session_presets"][PRESET].update(
        model="ollama/local"), FILTER),
    "retired opencode with home": (lambda c: c.variables.update(chaldea_client_session_profiles_absent=[
        {"name": "old", "driver": "opencode", "home": str(c.opencode_home)}]), FILTER),
    "native hash": (mutate(lambda p, c: p["native"].update(sha256="0" * 64)), "pinned size"),
    "native link": (lambda c: relink(c.opencode_native), "pinned size"),
    "shared home": (lambda c: c.opencode_home.chmod(0o755), "mode 0700"),
    "missing runtime": (lambda c: c.runtime.rmdir(), "mode 0700"),
}


@pytest.mark.parametrize("name", sorted(OPENCODE_REFUSALS))
def test_opencode_refused_before_any_profile_write(tmp_path, monkeypatch, name):
    case = opencode_layout(tmp_path, monkeypatch)
    change, message = OPENCODE_REFUSALS[name]
    change(case)
    result = run(case)
    assert result.returncode != 0, result.stdout
    assert message in result.stdout, result.stdout[-12000:]
    assert not case.opencode_dir.exists()


def test_mixed_profiles_and_opencode_inverse_leave_others_alone(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch, keep_codex=True)
    ok(run(case))
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    codex = {p.name: p.read_bytes() for p in case.directory.iterdir()}
    config = case.config.read_bytes()
    (case.runtime / "opencode-leftover").mkdir(mode=0o700)
    variables = case.variables | {
        "chaldea_client_session_profiles": {PROFILE: case.profile},
        "chaldea_client_session_profiles_absent": [{"name": OPENCODE, "driver": "opencode"}]}
    ok(run(case, entry="session-profiles-absent", check=True, variables=variables))
    assert (case.opencode_dir / "exec").exists()
    ok(run(case, entry="session-profiles-absent", variables=variables))
    assert not case.opencode_dir.exists() and case.opencode_native.exists()
    assert {p.name: p.read_bytes() for p in case.directory.iterdir()} == codex
    assert case.config.read_bytes() == config
    # The launcher-owned runtime directory and the profile home are never touched.
    assert [p.name for p in case.runtime.iterdir()] == ["opencode-leftover"]
    again = run(case, entry="session-profiles-absent", variables=variables)
    ok(again)
    assert "changed=0" in again.stdout, again.stdout


def test_opencode_inverse_refuses_foreign_paths(tmp_path, monkeypatch):
    case = opencode_layout(tmp_path, monkeypatch)
    ok(run(case))
    variables = case.variables | {"chaldea_client_session_profiles": {},
                                  "chaldea_client_session_profiles_absent": [{"name": OPENCODE, "driver": "opencode"}]}
    relink(case.opencode_dir / "opencode.json")
    result = run(case, entry="session-profiles-absent", variables=variables)
    assert result.returncode != 0 and "is not a role-owned profile path" in result.stdout, result.stdout[-8000:]
    assert all((case.opencode_dir / n).exists() for n in ("exec", "opencode", "opencode.json.saved"))
