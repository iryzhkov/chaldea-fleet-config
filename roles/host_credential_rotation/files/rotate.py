#!/usr/bin/env python3
"""Rotate the host's sole app password. No administrative credential or dependency."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ORIGIN = "https://auth.ryzhkov.dev"
CLIENT = "chaldea-host-rotation"
DAY = 86400


class Refused(Exception):
    pass


def require(ok):
    if not ok:
        raise Refused()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class API:
    def __init__(self, host):
        require(re.fullmatch(r"[a-z0-9-]+", host))
        self.host = host
        self.jwt = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, body=None, form=False):
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        if not form:
            headers["Authorization"] = "Bearer " + self.jwt
        req = urllib.request.Request(ORIGIN + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(1048577)
                require(len(raw) <= 1048576)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method in ("GET", "DELETE"):
                return None
            # Never include response bodies, request fields or exception text.
            raise Refused() from None

    def exchange(self, key):
        result = self.request("POST", "/application/o/token/", {
            "grant_type": "client_credentials", "client_id": CLIENT,
            "username": "chaldea-" + self.host, "password": key.decode(),
            "scope": "goauthentik.io/api"}, form=True)
        require(0 < result["expires_in"] <= 300)
        self.jwt = result["access_token"]

    def token(self, name, method="GET", body=None, key=False):
        require(re.fullmatch(r"[a-z0-9-]+", name))
        return self.request(method, "/api/v3/core/tokens/" + name + ("/view_key/" if key else "/"), body)

    def create(self, name, expires):
        self.request("POST", "/api/v3/core/tokens/", {
            "identifier": name, "intent": "app_password", "expiring": True,
            "expires": expires, "description": "Chaldea host self-rotation"})


def read(fd, name, optional=False):
    try:
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except FileNotFoundError:
        if optional:
            return None
        raise
    try:
        s = os.fstat(f)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
                and s.st_nlink == 1 and stat.S_IMODE(s.st_mode) == 0o600 and s.st_size <= 65536)
        return os.read(f, 65537)
    finally:
        os.close(f)


def atomic(fd, name, body):
    stage = name + ".stage"
    # A prior interrupted stage contains no authoritative state.
    try:
        os.unlink(stage, dir_fd=fd)
    except FileNotFoundError:
        pass
    f = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(f, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(stage, name, src_dir_fd=fd, dst_dir_fd=fd)
    os.fsync(fd)


def put(fd, name, value):
    atomic(fd, name, json.dumps(value, sort_keys=True).encode())


def remove(fd, name):
    try:
        os.unlink(name, dir_fd=fd)
        os.fsync(fd)
    except FileNotFoundError:
        pass


def directory(home):
    # Walk every ancestor without following symlinks.
    require(os.path.isabs(home) and os.path.normpath(home) == home)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in (home + "/.config/chaldea/authentik").strip("/").split("/"):
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
            s = os.fstat(fd)
            require(s.st_uid in (0, os.getuid()) and not s.st_mode & 0o022)
        s = os.fstat(fd)
        require(s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) == 0o700)
        return fd
    except BaseException:
        os.close(fd)
        raise


def rotate(fd, host, api, revoked=False, now=None, checkpoint=lambda _: None):
    now = now or dt.datetime.now(dt.timezone.utc)
    marker = json.loads(read(fd, "host.generation.json"))
    require(marker["host"] == host and marker["uid"] == os.getuid()
            and type(marker["generation"]) is int and marker["generation"] > 0)
    require(marker["status"] in ("committed", "revoked"))
    if revoked or marker["status"] == "revoked":
        marker["status"] = "revoked"
        put(fd, "host.generation.json", marker)
        for name in ("host.app-password", "host.app-password.stage", "rotation.json"):
            remove(fd, name)
        return
    current = read(fd, "host.app-password")
    raw = read(fd, "rotation.json", True)
    journal = json.loads(raw) if raw else None
    if journal:
        require(journal["host"] == host and journal["generation"] in
                (marker["generation"], marker["generation"] + 1))
    else:
        require(hashlib.sha256(current).hexdigest() == marker["sha256"])
    api.exchange(current)  # Inactive/expired credentials stop here, with no retry.
    old = journal["old"] if journal else marker.get("token", "chaldea-" + host + "-g" + str(marker["generation"]))
    if journal is None:
        token = api.token(old)
        require(token and token["intent"] == "app_password" and token["expiring"])
        expires = dt.datetime.fromisoformat(token["expires"].replace("Z", "+00:00"))
        if (expires - now).total_seconds() > 30 * DAY:
            return
        journal = {"host": host, "old": old, "new": "chaldea-" + host + "-g" + str(marker["generation"] + 1),
                   "generation": marker["generation"] + 1,
                   "expires": (now + dt.timedelta(days=59)).isoformat()}
        put(fd, "rotation.json", journal)  # Persist identity BEFORE a possibly uncertain POST.
    new = journal["new"]
    token = api.token(new)
    if token is None:
        api.create(new, journal["expires"])
        checkpoint("created")
    key = api.token(new, key=True)["key"].encode()
    require(16 <= len(key) <= 256 and all(33 <= b <= 126 for b in key))
    # Recovery accepts only the recorded current key or this generation's
    # server-staged replacement, never another valid credential for the user.
    require(hashlib.sha256(current).hexdigest() in
            (marker["sha256"], hashlib.sha256(key).hexdigest()))
    api.exchange(key)  # Verify before switching or deleting anything.
    checkpoint("verified")
    atomic(fd, "host.app-password", key)
    checkpoint("swapped")
    marker.update(generation=journal["generation"], status="committed",
                  token=new, sha256=hashlib.sha256(key).hexdigest())
    put(fd, "host.generation.json", marker)
    api.exchange(key)  # Revocation during the swap must prevent old-token cleanup.
    api.token(old, "DELETE")
    checkpoint("deleted")
    remove(fd, "rotation.json")


def acquire_lock(lock, revoked, timeout=120):
    deadline = time.monotonic() + (timeout if revoked else 0)
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            require(time.monotonic() < deadline)
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--revoked", action="store_true")
    args = parser.parse_args()
    fd = lock = None
    try:
        fd = directory(os.path.expanduser("~"))
        lock = os.open("host.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        s = os.fstat(lock)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
                and s.st_nlink == 1 and stat.S_IMODE(s.st_mode) == 0o600)
        acquire_lock(lock, args.revoked)
        rotate(fd, args.host, API(args.host), args.revoked)
    except Exception:
        # Fixed text only. The daily timer has no Restart policy.
        try:
            subprocess.run(["feed", "post",
                            "Host app credential rotation failed; inspect the host rotation service.",
                            "--severity", "fail", "--source", "feed"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise SystemExit(1) from None
    finally:
        if lock is not None:
            os.close(lock)
        if fd is not None:
            os.close(fd)


if __name__ == "__main__":
    main()
