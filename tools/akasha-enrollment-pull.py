#!/usr/bin/env python3
"""One explicit local pull. No passthrough Ansible arguments or recurring ownership."""
import json
import os
from pathlib import Path
import re
import socket
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
    allowed = {"akasha_enrollment_public_keys", "akasha_pc_global_reader_enabled", "akasha_pc_quota_events_enabled"}
    if not data or not data.keys() <= allowed or set(data.get("akasha_enrollment_public_keys", {})) != set(policy):
        raise ValueError("public keys required; no arbitrary extra-vars")
    if any(type(data.get(k, False)) is not bool for k in allowed - {"akasha_enrollment_public_keys"}):
        raise ValueError("boolean permission toggles required")
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
        os.execv(argv[0], argv)
    except (ValueError, OSError, KeyError, TypeError):
        sys.exit("akasha enrollment refused: check host/account/pin/public inputs")
