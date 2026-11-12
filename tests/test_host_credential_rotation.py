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
