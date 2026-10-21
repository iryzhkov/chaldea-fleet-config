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
        # Naming an explicit prohibition must not look like an execution handoff.
        execution_guidance = " ".join(text.split())
        for prohibition in (
            "Do not run `prepare` or `verify_run` when its configured pipeline "
            "would execute prohibited local project commands.",
            "Do not run prepare or `verify_run` when that pipeline would execute "
            "prohibited local project commands.",
        ):
            execution_guidance = execution_guidance.replace(prohibition, "")
        assert "verify_run" not in execution_guidance, path
        assert "debug_" not in text, path
        assert "chaldea exec --host agent-a" in text, path
        assert "HUYANG_FRICTION=0" in text, path
        assert "workspace_open" in text and "guarded edits" in text, path

    for path in ("agents/AGENTS.md", "codex/AGENTS.md", "skills/huyang/SKILL.md"):
        text = (FILES / path).read_text()
        assert "trust" in text and "prepared" in text, path
    skill = (FILES / "skills/huyang/SKILL.md").read_text()
    assert "format_gate" in skill and ".huyang.toml" in skill
    policy = " ".join(skill.split())
    assert "trusted by user policy in `~/.config/huyang/config.toml`" in policy
    assert "An untrusted root's skipped commands are missing evidence, never passes." in policy
    assert "Do not auto-trust a root or relax required gates." in policy
    assert "Chaldea results neither grant trust nor supply Huyang prepared-revision evidence." in policy


def test_local_selection_precedes_remote_execution():
    local_selector = "TEST_AFFECTED_LIST=1 make test-affected BASE=<pinned>"
    remote_tests = ("chaldea exec --host agent-a -- env "
                    "HUYANG_FRICTION=0 go test -race <pkgs>")
    for path in ("agents/AGENTS.md", "codex/AGENTS.md", "agents/huyang.md",
                 "claude/omarchy-setup/CLAUDE.md", "skills/huyang/SKILL.md"):
        flat = " ".join((FILES / path).read_text().split())
        assert "Chaldea jobs omit `.git`" in flat, path
        assert "selection/planning locally only when it does no build or test" in flat, path
        assert local_selector in flat and remote_tests in flat, path
        assert flat.index(local_selector) < flat.index(remote_tests), path
        assert "Keep the approved pinned base" in flat, path
        assert "Actual builds/tests run only in Chaldea" in flat, path
        assert "local selection is not verification" in flat, path
        assert "`check-fast` and `check-review` before dispatch" in flat, path
        assert "--artifact PATH" in flat and ".chaldea/artifacts/<job-id>/" in flat, path
        assert "guarded Huyang edits" in flat and "revision-guarded edit/change plan" in flat, path
        assert "Never overwrite repository source with shell commands" in flat, path
