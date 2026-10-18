#!/usr/bin/env python3
"""One explicit local pull. No passthrough Ansible arguments or recurring ownership."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

def command(args, hostname, uid, home):
    if len(args) not in (4, 5) or (len(args) == 5 and args[4] != "--check"):
        raise ValueError("HOST SHA PUBLIC_INPUTS stage|activate [--check]")
    host, sha, path, mode = args[:4]
    policy = json.loads((Path(__file__).resolve().parents[1] / "access-trust/akasha-enrollment.json").read_text())
    if host not in policy or mode not in ("stage", "activate") or not re.fullmatch("[a-f0-9]{40}", sha):
        raise ValueError("exact approved host, commit and mode required")
    row = policy[host]
    if (hostname, uid, home) != (host, row["uid"], row["home"]):
        raise ValueError("run locally as the exact producer account")
    inputs = Path(path)
    if not inputs.is_absolute() or not inputs.is_file():
        raise ValueError("absolute public input file required")
    data = json.loads(inputs.read_text())
    allowed = {"akasha_enrollment_public_keys", "akasha_pc_global_reader_enabled", "akasha_pc_quota_events_enabled",
               "akasha_quota_laptop_publisher_enabled", "akasha_quota_pc_reader_enabled",
               "akasha_quota_runtime_version", "akasha_quota_runtime_sha256"}
    if not isinstance(data, dict) or not data.keys() <= allowed or not isinstance(data.get("akasha_enrollment_public_keys"), dict) or set(data["akasha_enrollment_public_keys"]) != set(policy):
        raise ValueError("public keys required; no arbitrary extra-vars")
    if any(type(data.get(k, False)) is not bool for k in allowed - {"akasha_enrollment_public_keys", "akasha_quota_runtime_version", "akasha_quota_runtime_sha256"}):
        raise ValueError("boolean permission toggles required")
    if any(not isinstance(data.get(k, ""), str) for k in ("akasha_quota_runtime_version", "akasha_quota_runtime_sha256")):
        raise ValueError("public quota release pins must be strings")
    return [home + "/.local/share/chaldea/ansible-core-2.19.14/bin/ansible-pull",
            "--url", "https://github.com/iryzhkov/chaldea-fleet-config.git", "--checkout", sha,
            "--directory", home + "/.cache/chaldea/akasha-enrollment",
            "--inventory", "inventory/akasha-enrollment.yml", "--limit", host,
            "--extra-vars", "@" + str(inputs),
            "--extra-vars", json.dumps({"akasha_enrollment_enabled": True, "akasha_enrollment_activate": mode == "activate"}),
            *(["--check", "--diff"] if len(args) == 5 else []), "playbooks/akasha-enrollment.yml"]

if __name__ == "__main__":
    try:
        argv = command(sys.argv[1:], socket.gethostname(), os.getuid(), os.path.expanduser("~"))
        if sys.argv[4] == "activate":
            main = subprocess.run(["git", "ls-remote", "https://github.com/iryzhkov/chaldea-fleet-config.git", "refs/heads/main"],
                                  check=True, capture_output=True, text=True).stdout.strip()
            if main != sys.argv[2] + "\trefs/heads/main":
                raise ValueError("activation requires the current main commit")
        os.execv(argv[0], argv)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError):
        sys.exit("akasha enrollment refused: check host/account/pin/public inputs")
