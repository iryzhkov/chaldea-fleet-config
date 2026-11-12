"""Fake Authentik plus real private filesystem, with no network or real HOME."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("rotation", Path(__file__).resolve().parents[1] /
    "roles/host_credential_rotation/files/rotate.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
NOW = dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc)


class Crash(BaseException):
    pass


class Fake:
    def __init__(self):
        self.active = True
        self.expired = False
        self.tokens = {"chaldea-agent-b-g1": b"SYNTHETIC-original-password"}
        self.created = 0
        self.fail = None

    def exchange(self, key):
        if not self.active or self.expired or key not in self.tokens.values():
            raise r.Refused()

    def token(self, name, method="GET", body=None, key=False):
        if not self.active:
            raise r.Refused()
        if method == "DELETE":
            self.tokens.pop(name, None)
            return {}
        if name not in self.tokens:
            return None
        if key:
            return {"key": self.tokens[name].decode()}
        return {"intent": "app_password", "expiring": True,
                "expires": (NOW + dt.timedelta(days=1)).isoformat()}

    def create(self, name, expires):
        assert name not in self.tokens
        assert dt.datetime.fromisoformat(expires) <= NOW + dt.timedelta(days=60)
        self.created += 1
        self.tokens[name] = b"SYNTHETIC-replacement-password"


@pytest.fixture
def custody(tmp_path):
    os.chmod(tmp_path, 0o700)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    key = b"SYNTHETIC-original-password"
    r.atomic(fd, "host.app-password", key)
    r.put(fd, "host.generation.json", {"host": "agent-b", "uid": os.getuid(),
        "generation": 1, "status": "committed", "sha256": hashlib.sha256(key).hexdigest()})
    yield fd, Fake()
    os.close(fd)


def run(fd, api, **kw):
    r.rotate(fd, "agent-b", api, now=NOW, **kw)


@pytest.mark.parametrize("point", [None, "created", "verified", "swapped", "deleted"])
def test_routine_and_crashes(custody, point):
    fd, api = custody
    def crash(stage):
        if stage == point:
            raise Crash()
    if point:
        with pytest.raises(Crash):
            run(fd, api, checkpoint=crash)
    run(fd, api)
    assert api.created == 1
    assert set(api.tokens) == {"chaldea-agent-b-g2"}
    marker = json.loads(r.read(fd, "host.generation.json"))
    assert marker["generation"] == 2
    assert marker["sha256"] == hashlib.sha256(r.read(fd, "host.app-password")).hexdigest()
    assert r.read(fd, "rotation.json", True) is None
    assert len(os.listdir(fd)) == 2


@pytest.mark.parametrize("point", ["created", "swapped"])
def test_revoke_pending_and_stale_inventory(custody, point):
    fd, api = custody
    def crash(stage):
        if stage == point:
            api.active = False
            raise Crash()
    with pytest.raises(Crash):
        run(fd, api, checkpoint=crash)
    with pytest.raises(r.Refused):
        run(fd, api)
    run(fd, api, revoked=True)
    # A stale revoked=false pull cannot undo the local tombstone.
    api.active = True
    run(fd, api, revoked=False)
    assert r.read(fd, "host.app-password", True) is None
    assert r.read(fd, "rotation.json", True) is None
    assert json.loads(r.read(fd, "host.generation.json"))["status"] == "revoked"


def test_offline_expired_stays_off(custody):
    fd, api = custody
    api.expired = True
    for _ in range(2):
        with pytest.raises(r.Refused):
            run(fd, api)
    assert api.created == 0
    assert len(api.tokens) == 1


def test_symlink_and_hardlink_refused(custody, tmp_path):
    fd, api = custody
    r.remove(fd, "host.app-password")
    (tmp_path / "foreign").write_bytes(b"SYNTHETIC-password")
    (tmp_path / "host.app-password").symlink_to("foreign")
    with pytest.raises(OSError):
        run(fd, api)
    (tmp_path / "host.app-password").unlink()
    os.link(tmp_path / "foreign", tmp_path / "host.app-password")
    with pytest.raises(r.Refused):
        run(fd, api)


def test_failure_feed_contains_no_exception_or_secret(custody, monkeypatch):
    import sys
    fd, _ = custody
    monkeypatch.setattr(sys, "argv", ["rotate.py", "--host", "agent-b"])
    monkeypatch.setattr(r, "directory", lambda _: os.dup(fd))
    def fail(*args, **kw):
        raise r.Refused("SYNTHETIC-secret-must-not-appear")
    monkeypatch.setattr(r, "rotate", fail)
    calls = []
    monkeypatch.setattr(r.subprocess, "run", lambda argv, **kw: calls.append(argv))
    with pytest.raises(SystemExit):
        r.main()
    assert len(calls) == 1
    assert calls[0][:2] == ["feed", "post"]
    assert calls[0][-4:] == ["--severity", "fail", "--source", "feed"]
    assert "SYNTHETIC" not in str(calls)


@pytest.mark.parametrize("error", [FileNotFoundError, r.subprocess.TimeoutExpired])
def test_feed_unavailable_exits_cleanly(custody, monkeypatch, error):
    import sys
    fd, _ = custody
    monkeypatch.setattr(sys, "argv", ["rotate.py", "--host", "agent-b"])
    monkeypatch.setattr(r, "directory", lambda _: os.dup(fd))
    monkeypatch.setattr(r, "rotate", lambda *a: (_ for _ in ()).throw(r.Refused()))
    def fail(*a, **kw):
        if error is r.subprocess.TimeoutExpired:
            raise error("feed", 20)
        raise error("feed")
    monkeypatch.setattr(r.subprocess, "run", fail)
    with pytest.raises(SystemExit) as exc:
        r.main()
    assert exc.value.code == 1


def test_revocation_waits_for_real_flock(custody, monkeypatch):
    import sys
    import threading
    fd, _ = custody
    held = os.open("host.lock", os.O_RDWR | os.O_CREAT, 0o600, dir_fd=fd)
    r.fcntl.flock(held, r.fcntl.LOCK_EX)
    monkeypatch.setattr(sys, "argv", ["rotate.py", "--host", "agent-b", "--revoked"])
    monkeypatch.setattr(r, "directory", lambda _: os.dup(fd))
    timer = threading.Timer(0.2, lambda: r.fcntl.flock(held, r.fcntl.LOCK_UN))
    timer.start()
    try:
        r.main()
        assert r.read(fd, "host.app-password", True) is None
        assert json.loads(r.read(fd, "host.generation.json"))["status"] == "revoked"
    finally:
        timer.join()
        os.close(held)


def test_held_flock_timeout_refuses(custody):
    fd, _ = custody
    held = os.open("host.lock", os.O_RDWR | os.O_CREAT, 0o600, dir_fd=fd)
    contender = os.open("host.lock", os.O_RDWR, dir_fd=fd)
    try:
        r.fcntl.flock(held, r.fcntl.LOCK_EX)
        with pytest.raises(r.Refused):
            r.acquire_lock(contender, True, timeout=0.1)
        assert r.read(fd, "host.app-password")
        assert json.loads(r.read(fd, "host.generation.json"))["status"] == "committed"
    finally:
        os.close(contender)
        os.close(held)


def test_pending_journal_refuses_unrelated_valid_key(custody):
    fd, api = custody
    def crash(stage):
        if stage == "created":
            raise Crash()
    with pytest.raises(Crash):
        run(fd, api, checkpoint=crash)
    foreign = b"SYNTHETIC-unrelated-valid-password"
    api.tokens["foreign"] = foreign
    r.atomic(fd, "host.app-password", foreign)
    with pytest.raises(r.Refused):
        run(fd, api)
    assert r.read(fd, "host.app-password") == foreign
    assert len(api.tokens) == 3


def test_expiry_has_clock_skew_margin(custody):
    fd, api = custody
    original = api.create
    def create(name, expires):
        assert dt.datetime.fromisoformat(expires) == NOW + dt.timedelta(days=59)
        original(name, expires)
    api.create = create
    run(fd, api)


def test_fresh_token_no_rotation(custody):
    fd, api = custody
    original = api.token
    def token(*args, **kw):
        result = original(*args, **kw)
        result["expires"] = (NOW + dt.timedelta(days=45)).isoformat()
        return result
    api.token = token
    run(fd, api)
    assert api.created == 0
