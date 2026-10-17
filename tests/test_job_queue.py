"""Real protocol/lock tests; no sandbox, host config, or real HOME writes."""
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import time

SERVER = Path(__file__).resolve().parents[1] / "roles/chaldea_job_host/files/chaldea-job-server"
DRIVER = """
import importlib.machinery,importlib.util,json,sys
loader=importlib.machinery.SourceFileLoader("server",sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
s=importlib.util.module_from_spec(spec);loader.exec_module(s)
s.admission=lambda *args: None
def execute(request,workspace,config):
    with open(config["launch_log"],"a") as log: log.write(request["jobId"]+"\\n")
    return 0
s.execute=execute
sys.argv=["server","--config",sys.argv[2]]
try: s.main()
except Exception as e:
    s.send("R",s.encode({"outcome":"refused","message":str(e)}))
"""
REQUEST = {"version": 1, "jobId": "11111111-1111-1111-1111-111111111111",
           "argv": ["true"], "cwd": "", "gpu": False, "files": [], "artifacts": []}


def send(child, kind, value=None):
    body = b"" if value is None else json.dumps(value).encode()
    child.stdin.write(kind.encode() + struct.pack("!I", len(body)) + body)
    child.stdin.flush()


def receive(child, timeout=3):
    def exact(size):
        result = b""
        deadline = time.monotonic() + timeout
        while len(result) < size:
            assert select.select([child.stdout], [], [], max(0, deadline - time.monotonic()))[0], "frame timed out"
            data = os.read(child.stdout.fileno(), size - len(result))
            assert data, "protocol EOF"
            result += data
        return result
    header = exact(5)
    body = exact(struct.unpack("!I", header[1:])[0])
    return chr(header[0]), json.loads(body) if body else None


def start(tmp_path, slots=1, seconds=3, queued=True):
    home = tmp_path / "home"
    assert home.parent == tmp_path and tmp_path.is_absolute()
    home.mkdir(exist_ok=True)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"state_root": str(tmp_path / "jobs"), "require_mount": False,
                                  "slots": slots, "launch_log": str(tmp_path / "launches")}))
    (tmp_path / "jobs").mkdir(exist_ok=True)
    child = subprocess.Popen([sys.executable, "-I", "-c", DRIVER, str(SERVER), str(config)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env={**os.environ, "HOME": str(home),
                                  "SSH_ORIGINAL_COMMAND": "chaldea-exec-queue-v1" if queued else "chaldea-exec-v0"},
                             bufsize=0)
    if queued:
        assert receive(child) == ("H", {"version": 1, "queueVersion": 1})
        send(child, "W", {"version": 1, "timeoutSeconds": seconds})
    return child


def close(child):
    child.stdin.close()
    child.wait(timeout=3)
    child.stdout.close()
    child.stderr.close()


def lock(tmp_path, slot=0):
    root = tmp_path / "jobs"
    root.mkdir(exist_ok=True)
    file = (root / ("admission.lock" if slot == 0 else f"admission-{slot}.lock")).open("a")
    fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return file


def test_any_slot_release_wakes_within_two_seconds_and_go_is_required(tmp_path):
    first, second = lock(tmp_path), lock(tmp_path, 1)
    child = start(tmp_path, slots=2)
    try:
        assert not select.select([child.stdout], [], [], .1)[0]
        start_time = time.monotonic()
        second.close()
        assert receive(child)[0] == "Y"
        assert time.monotonic() - start_time < 2
        assert not (tmp_path / "launches").exists()
        send(child, "G")
        send(child, "Q", REQUEST)
        send(child, "E")
        assert receive(child) == ("X", {"exitCode": 0})
        assert (tmp_path / "launches").read_text().splitlines() == [REQUEST["jobId"]]
    finally:
        first.close()
        second.close()
        close(child)


def test_disconnect_blocked_and_ready_releases_all_waiters_without_launch(tmp_path):
    for ready in (False, True):
        held = lock(tmp_path)
        child = start(tmp_path, seconds=10)
        if ready:
            held.close()
            assert receive(child)[0] == "Y"
        close(child)
        held.close()
        with lock(tmp_path):
            pass
        assert not (tmp_path / "launches").exists()


def test_cancel_and_queue_timeout_launch_nothing(tmp_path):
    held = lock(tmp_path)
    try:
        child = start(tmp_path, seconds=.15)
        assert receive(child) == ("R", {"outcome": "refused", "message": "queue timeout"})
        close(child)
        child = start(tmp_path)
        send(child, "C")
        assert receive(child)[0] == "R"
        close(child)
        assert not (tmp_path / "launches").exists()
    finally:
        held.close()


def test_old_client_still_runs(tmp_path):
    child = start(tmp_path, queued=False)
    assert receive(child) == ("H", {"version": 1})
    send(child, "Q", REQUEST)
    send(child, "E")
    assert receive(child) == ("X", {"exitCode": 0})
    close(child)
