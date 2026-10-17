#!/usr/bin/env python3
"""Fetch signed bytes only; never check out or execute remote repository content."""
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys

REMOTE = "ssh://git@github.com/iryzhkov/chaldea-fleet-config.git"
REF = "refs/heads/trust-source"
BUNDLE = "access-trust/bundle.jws"
MAX_BUNDLE = 262144


def trusted(path, private=False):
    info = Path(path).lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or info.st_mode & (0o077 if private else 0o022)):
        raise ValueError("unsafe input")


def fetch(config):
    state = Path(config["state"])
    info = state.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise ValueError("unsafe state")
    trusted(config["key"], private=True)
    trusted(config["known_hosts"])
    cache = state / "git"
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(state), "TMPDIR": str(state),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
        "GIT_SSH_COMMAND": shlex.join([
            "/usr/bin/ssh", "-F", "/dev/null", "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + config["known_hosts"],
            "-i", config["key"],
        ]),
    }

    def git(*args):
        return subprocess.run([
            "/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "gc.auto=0",
            "-c", "protocol.allow=never", "-c", "protocol.ssh.allow=always",
            *args,
        ], env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20).stdout

    if not cache.exists():
        git("init", "--bare", "--template=", str(cache))
    git("--git-dir=" + str(cache), "fetch", "--depth=1", "--no-tags",
        "--no-recurse-submodules", REMOTE, "+refs/heads/main:" + REF)
    commit = git("--git-dir=" + str(cache), "rev-parse", "--verify", REF).decode().strip()
    obj = commit + ":" + BUNDLE
    size = int(git("--git-dir=" + str(cache), "cat-file", "-s", obj))
    if size < 1 or size > MAX_BUNDLE:
        raise ValueError("bundle size")
    envelope = git("--git-dir=" + str(cache), "cat-file", "blob", obj)
    if len(envelope) != size:
        raise ValueError("bundle changed")
    # Bound the byte-only transport cache; never prune security state.
    git("--git-dir=" + str(cache), "reflog", "expire", "--expire=now", "--all")
    git("--git-dir=" + str(cache), "gc", "--prune=now", "--quiet")
    candidate = state / "candidate.jws"
    # state is private and trusted; never write a candidate in the public directory.
    fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(envelope)
    except BaseException:
        candidate.unlink(missing_ok=True)
        raise
    try:
        subprocess.run([
            config["node"], config["runtime"], "install-bundle",
            "--state-file", str(state / "updater.sqlite"),
            "--clock-health-file", config["health"],
            "--anchor-file", config["anchors"], "--bundle-file", str(candidate),
            "--output", config["output"],
        ], env=env, check=True, timeout=15)
    finally:
        candidate.unlink(missing_ok=True)


def main():
    try:
        os.umask(0o077)
        trusted(sys.argv[1])
        config = json.loads(Path(sys.argv[1]).read_text())
        fetch(config)
    except Exception:
        # Do not expose credentials, signed inputs or subprocess output on failure.
        print("chaldea trust: update failed; cached signed expiry is unchanged", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
