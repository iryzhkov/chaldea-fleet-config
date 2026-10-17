"""Guard shared Huyang guidance and the role's maintained derived copies."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "roles/agent_config/files"


def test_resident_summary_reaches_codex():
    shared = (FILES / "agents/AGENTS.md").read_text()
    codex = (FILES / "codex/AGENTS.md").read_text()
    assert codex == "<!-- fleet:start -->\n" + shared + "<!-- fleet:end -->\n"


def test_reference_matches_role_sources():
    claude = (FILES / "claude/omarchy-setup/CLAUDE.md").read_text()
    skill = (FILES / "skills/huyang/SKILL.md").read_text()
    reference = (FILES / "agents/huyang.md").read_text()
    section = claude[claude.index("# Reading and editing code\n"):]
    skill_body = skill.split("---\n", 2)[2]
    assert reference.endswith(section + "\n---\n\n" + skill_body)
    assert "Maintained in chaldea-fleet-config" in reference
    assert "do not regenerate over fleet-managed files" in reference


def test_removed_tools_and_execution_handoff():
    for path in ("agents/AGENTS.md", "codex/AGENTS.md", "agents/huyang.md",
                 "claude/omarchy-setup/CLAUDE.md", "skills/huyang/SKILL.md"):
        text = (FILES / path).read_text()
        assert "verify_run" not in text, path
        assert "debug_" not in text, path
        assert "chaldea exec --host agent-a" in text, path
        assert "HUYANG_FRICTION=0" in text, path
        assert "workspace_open" in text and "guarded edits" in text, path

    for path in ("agents/AGENTS.md", "codex/AGENTS.md", "skills/huyang/SKILL.md"):
        text = (FILES / path).read_text()
        assert "trust" in text and "prepared" in text, path
    skill = (FILES / "skills/huyang/SKILL.md").read_text()
    assert "format_gate" in skill and ".huyang.toml" in skill
    assert "huyang trust <root>" in skill
    assert "untrusted root skips" in skill
    assert "does not grant trust or replace prepared-revision evidence" in skill
