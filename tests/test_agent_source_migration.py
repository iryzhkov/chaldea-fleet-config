"""Compare source and rendered host instructions with the current byte snapshot."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "roles/agent_config/files"
BEFORE = json.loads((ROOT / "tests/fixtures/agent_config_before.json").read_text())
DESTINATIONS = {
    "claude/omarchy-setup/CLAUDE.md": ".claude/omarchy-setup/CLAUDE.md",
    "codex/AGENTS.md": ".codex/AGENTS.md",
    "agents/AGENTS.md": ".config/agents/AGENTS.md",
    "agents/jocasta.md": ".config/agents/jocasta.md",
    "agents/huyang.md": ".config/agents/huyang.md",
    "agents/ov-memory.md": ".config/agents/ov-memory.md",
    "bin/opencode": ".local/bin/opencode",
    "opencode/huyang-profiles.js": ".config/opencode/plugins/huyang-profiles.js",
}
ADDED_FILES = set()
COMPACT_RUNTIME = json.loads((ROOT / 'tests/fixtures/agent_config_compact_runtime.json').read_text())

def compare(relative, data):
    baseline_path = "roles/agent_config/files/" + relative
    assert hashlib.sha256(data).hexdigest() == BEFORE["files"][baseline_path], relative


def test_source_matches_current_snapshot():
    paths = {p.relative_to(ROOT).as_posix() for p in FILES.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    assert paths == BEFORE["files"].keys() | {"roles/agent_config/files/" + p for p in ADDED_FILES}
    for path in BEFORE["files"]:
        compare(Path(path).relative_to("roles/agent_config/files").as_posix(), (ROOT / path).read_bytes())


@pytest.mark.parametrize("host", ["agent-a", "agent-b", "omarchy-pc", "laptop"])
def test_before_after_render_for_every_host(tmp_path, host):
    assert Path.home().is_relative_to(tmp_path.parent)
    home = tmp_path / host
    play = tmp_path / "render.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Render source migration into a disposable host home",
        "hosts": host, "gather_facts": False,
        "tasks": [{"name": "Render the fleet-owned agent configuration",
                   "ansible.builtin.include_role": {"name": "agent_config"}}],
    }]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    result = subprocess.run([
        "ansible-playbook", "-i", str(ROOT / "inventory"), "--limit", host,
        str(play), "--extra-vars", json.dumps({"fleet_home": str(home)}),
    ], text=True, capture_output=True, env=env, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    defaults = yaml.safe_load((ROOT / "roles/agent_config/defaults/main.yml").read_text())
    assert {entry["src"]: entry["dest"] for entry in defaults["agent_config_files"]} == {
        source: dest for source, dest in DESTINATIONS.items() if source != "opencode/huyang-profiles.js"}
    for source, destination in DESTINATIONS.items():
        compare(source, (home / destination).read_bytes())
    for target in (".agents", ".claude"):
        assert_delegation_contract(lambda path: (
            home / (DESTINATIONS[path] if path in DESTINATIONS else target + "/" + path)
        ).read_text())
    skill_files = [p for p in BEFORE["files"] if "/files/skills/" in p]
    for path in skill_files:
        relative = Path(path).relative_to("roles/agent_config/files").as_posix()
        for target in (".agents", ".claude"):
            compare(relative, (home / target / relative).read_bytes())
    for relative in ADDED_FILES:
        for target in (".agents", ".claude"):
            installed = home / target / relative
            assert installed.is_file() and not installed.parent.is_symlink()
            assert installed.read_bytes() == (FILES / relative).read_bytes()


def assert_delegation_contract(read):
    """The three instruction entry points and installed skills must agree."""
    instructions = [read(path) for path in (
        "agents/AGENTS.md", "codex/AGENTS.md", "claude/omarchy-setup/CLAUDE.md")]
    runtime = read("skills/agent-workflow/references/interactive-runtime.md")
    assert COMPACT_RUNTIME["before"] in runtime
    for text in instructions:
        assert COMPACT_RUNTIME["after"] in text
        assert "references/interactive-runtime.md" in text
    instructions = [text.replace(COMPACT_RUNTIME["after"], COMPACT_RUNTIME["before"], 1)
                    for text in instructions]
    execution = [text.split("Work happens in interactive T3 sessions.", 1)[1]
                 .split("Before each T3 `delegate_task`", 1)[0] for text in instructions]
    assert execution[0] == execution[1] == execution[2]
    # Delegation alone must not select the roadmap lifecycle or demand a checkpoint.
    for text in instructions:
        assert "When you own root orchestration, load roadmap-executor first." not in text
        assert "When executing an adopted roadmap as root, load roadmap-executor first." in text
    reporting = [text.split("rounds. Preserve every reviewer's", 1)[1]
                 .split("After an accepted review", 1)[0] for text in instructions]
    assert reporting[0] == reporting[1] == reporting[2]
    for field in ("task/thread IDs", "model", "verdict", "reviewed commit",
                  "durable receipt", "receipt link in chat"):
        assert field in reporting[0]
    authority = [text.split("Igor grants standing authority", 1)[1]
                 .split("\n\n", 1)[0] for text in instructions]
    assert authority[0] == authority[1] == authority[2]
    routing = [text.split("Before each T3 `delegate_task`", 1)[1]
               .split("Delegate through T3", 1)[0] for text in instructions]
    assert routing[0] == routing[1] == routing[2]
    skills = [read("skills/" + name + "/SKILL.md")
              for name in ("chaldea", "review-delegation")]
    # roadmap-executor defers to the shared section instead of carrying a copy that could drift.
    roadmap = read("skills/roadmap-executor/SKILL.md")
    assert "`providerInstanceId`" not in roadmap and "FATE before every `delegate_task`" in roadmap
    assert "Use this while executing an adopted roadmap as its root orchestrator" in roadmap
    review_description = yaml.safe_load(skills[1].split("---", 2)[1])["description"]
    assert "interactive T3 work" in review_description
    assert "carrying out an agreed plan" not in review_description
    # The shorter chat rule must retain durable review evidence, including quota exceptions.
    review_reporting = skills[1].split("## Quota exception", 1)[1].split(
        "## Check necessity", 1)[0]
    for field in ("task/thread IDs", "model", "verdict", "reviewed commit",
                  "durable receipt", "receipt link in chat"):
        assert field in review_reporting
    assert "in the reply and PR comment" not in skills[1]
    for text in instructions + skills:
        text = " ".join(text.split())
        for field in ("`providerInstanceId`", "`model`", "`options`"):
            assert field in text
        assert "--author-provider" in text
        assert "exactly as" in text and "including effort" in text
        assert "installed CLI" in text and "Quota exception" in text
        assert "Reject a same-provider target" in text
        assert "underlying provider drivers" in text
        assert "Maximum effort is high; only Luna/Haiku may use xhigh." in text
        assert "These are ceilings, not defaults." in text
        assert "Haiku needs an available catalog target." in text
        assert "Never use max, ultra, ultrathink or ultracode." in text
        assert "The client pins builder to" not in text
        assert "Model roles:" not in text
    review = skills[1]
    for required in ("builder --author-provider codex", "Opus 5.5 medium",
                     "Opus 5.5 high and Astra medium",
                     "Sol 6.1 high", "two different models on the same provider",
                     "fresh quota evidence", "one independent review is acceptable",
                     "fresh independent context", "At most two fix rounds",
                     "No spending, reset redemption or authentication changes"):
        assert required in review
    assert "HTTP 429 alone grant no waiver" in skills[0]
    assert "Never invent a reset timestamp" in review
    assert "Astra/Fable are not mandatory normal reviewers." in review
    assert "Current router critical-review defaults still use Fable" in review
    assert "one target plus alternatives/byProvider" in review
    assert "mandatory normal reviewers" in review


def test_canonical_delegation_contract():
    assert_delegation_contract(lambda path: (FILES / path).read_text())
