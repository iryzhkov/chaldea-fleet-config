"""Exercise canonical guidance selection, host identity and link guards in scratch."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

import pytest
import yaml

from test_agent_skills import ROOT, SKILLS, scratch


def invoke(home, *, check=False, wrong_host=False):
    base = scratch()
    inventory = base / "guidance-inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"children": {"agent_hosts": {"hosts": {
        "laptop": {
            "ansible_connection": "local",
            "ansible_python_interpreter": sys.executable,
            "expected_hostname": "wrong-machine" if wrong_host else socket.gethostname().split(".")[0],
            "fleet_home": str(home),
        }
    }}}}}))
    selected = base / "selected-guidance.json"
    selected.write_text(json.dumps({
        "agent_config_files": [{"src": "agents/AGENTS.md", "dest": ".config/agents/AGENTS.md"}],
        "agent_config_skills": ["tdd"],
        "agent_config_skill_dirs": [".claude/skills", ".agents/skills"],
    }))
    argv = ["ansible-playbook", "-i", str(inventory), str(ROOT / "site.yml"),
            "--limit", "laptop", "--tags", "agent_guidance", "--extra-vars", "@" + str(selected)]
    if check:
        argv += ["--check", "--diff"]
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True,
                            env={**os.environ, "ANSIBLE_LOCAL_TEMP": str(base / "ansible")})
    return result.returncode, result.stdout + result.stderr


def files(home):
    return {p.relative_to(home).as_posix(): p.read_bytes()
            for p in home.rglob("*") if p.is_file()}


def test_guidance_tag_only_installs_selected_bytes_and_is_idempotent():
    home = scratch() / "fleet"
    # These would be changed by retirement, plugin or generated-tool convergence.
    sentinels = {".claude/skills/code-review/keep": b"retained",
                 ".config/opencode/plugins/huyang-profiles.js": b"local plugin",
                 ".agents/skills/fleet-tools/SKILL.md": b"retained discovery",
                 ".local/bin/opencode": b"retained wrapper"}
    for relative, data in sentinels.items():
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    code, output = invoke(home, check=True)
    assert code == 0, output
    assert files(home) == sentinels
    assert "Refuse to apply another host's configuration" in output
    for forbidden in ("Retire explicitly removed skills", "Distribute the owned OpenCode",
                      "Generate installed custom tool discovery"):
        assert forbidden not in output
    code, output = invoke(home)
    assert code == 0, output
    expected = dict(sentinels)
    expected[".config/agents/AGENTS.md"] = (ROOT / "roles/agent_config/files/agents/AGENTS.md").read_bytes()
    for directory in (".claude/skills", ".agents/skills"):
        for source in (SKILLS / "tdd").rglob("*"):
            if source.is_file():
                relative = directory + "/tdd/" + source.relative_to(SKILLS / "tdd").as_posix()
                expected[relative] = source.read_bytes()
                assert (home / relative).stat().st_mode & 0o777 == 0o644
        assert (home / directory / "tdd").stat().st_mode & 0o777 == 0o755
    assert files(home) == expected
    code, output = invoke(home)
    assert code == 0, output
    assert re.search(r"laptop\s+: ok=\d+\s+changed=0\s+unreachable=0\s+failed=0", output), output
    assert files(home) == expected


@pytest.mark.parametrize("wrong_host", [True, False])
def test_guidance_tag_refuses_wrong_host_or_modified_laptop_link(wrong_host):
    home = scratch() / "fleet"
    target = home / ".agents/skills/tdd"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("unapproved local content")
    link = home / ".claude/skills/tdd"
    link.parent.mkdir(parents=True)
    link.symlink_to("../../.agents/skills/tdd", target_is_directory=True)
    before = files(home)
    for check in (True, False):
        code, output = invoke(home, check=check, wrong_host=wrong_host)
        assert code != 0, output
        assert link.is_symlink()
        assert (target / "SKILL.md").read_text() == "unapproved local content"
        if wrong_host:
            assert files(home) == before
            assert not (home / ".config").exists()
        else:
            assert "Require the full skill target tree" in output
