"""Narrow retired-command removal against the real inventory, in a scratch home.

The Jocasta CLI is retired only on the laptop and omarchy-pc. The canonical
site.yml tag must run that one removal and nothing else from agent_tools or
any other role, keep the actual-host identity check, and repeat without change.
"""
import json
import os
import re
import socket
import subprocess

import pytest
import yaml

from test_agent_skills import ROOT, scratch

TAG = "agent_tools_retired_commands"
DEFAULT_RETIRED = yaml.safe_load(
    (ROOT / "roles/agent_tools/defaults/main.yml").read_text())["agent_tools_retired_commands"]
# Every command the role default retires, the Jocasta CLI and its private
# files, a command the role links and a release the role would otherwise prune.
SEED = {**{".local/bin/" + name: b"retired" for name in DEFAULT_RETIRED},
        ".local/bin/jocasta": b"legacy cli",
        ".config/jocasta/config.json": b"{}",
        ".config/jocasta/token": b"synthetic",
        ".local/bin/feed": b"homelab-cli command",
        ".local/share/agent-tools/older/.complete": b"",
        ".local/share/agent-tools/oldest/.complete": b""}
UNRELATED = ("Check the SSH aliases", "Check whether the pinned release is already built",
             "Point current at the pinned release", "Link homelab-cli commands",
             "Link MCP server launchers", "Find agent tools releases",
             "Check the credential files", "Generate installed custom tool discovery")


def invoke(host, home, *, check=False, wrong_host=False):
    base = scratch()
    hostname = "wrong-machine" if wrong_host else socket.gethostname().split(".")[0]
    argv = ["ansible-playbook", "-i", str(ROOT / "inventory"), str(ROOT / "site.yml"),
            "--limit", host, "--tags", TAG,
            "--extra-vars", json.dumps({"fleet_home": str(home), "expected_hostname": hostname})]
    if check:
        argv += ["--check", "--diff"]
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True,
                            env={**os.environ, "ANSIBLE_LOCAL_TEMP": str(base / "ansible")})
    return result.returncode, result.stdout + result.stderr


def seeded():
    home = scratch() / "fleet"
    for relative, data in SEED.items():
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return home


def tree(home):
    return {p.relative_to(home).as_posix(): None if p.is_dir() else p.read_bytes()
            for p in home.rglob("*")}


def without(before, *names):
    return {path: data for path, data in before.items()
            if path not in {".local/bin/" + name for name in names}}


@pytest.mark.parametrize("host", ["laptop", "omarchy-pc"])
def test_tag_removes_only_retired_commands_and_repeats_unchanged(host):
    home = seeded()
    before = tree(home)
    code, output = invoke(host, home, check=True)
    assert code == 0, output
    assert tree(home) == before
    assert "Refuse to apply another host's configuration" in output
    assert "Remove commands of retired tools" in output
    for name in UNRELATED:
        assert name not in output
    expected = without(before, *DEFAULT_RETIRED, "jocasta")
    for _ in range(2):
        code, output = invoke(host, home)
        assert code == 0, output
        assert tree(home) == expected
    assert re.search(host + r"\s+: ok=\d+\s+changed=0\s+unreachable=0\s+failed=0", output), output


@pytest.mark.parametrize("host", ["agent-a", "agent-b", "homelab", "normandy"])
def test_other_hosts_keep_the_jocasta_cli(host):
    home = seeded()
    before = tree(home)
    code, output = invoke(host, home)
    assert code == 0, output
    assert tree(home) == without(before, *DEFAULT_RETIRED)


@pytest.mark.parametrize("check", [True, False])
def test_tag_refuses_another_machine_without_change(check):
    home = seeded()
    before = tree(home)
    code, output = invoke("laptop", home, check=check, wrong_host=True)
    assert code != 0, output
    assert "limit the run to this machine's entry" in output
    assert tree(home) == before
