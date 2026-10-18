"""The seven recorded laptop links migrate only after exact TDD restoration."""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from test_agent_skills import SKILLS, laptop_layout, run_role, scratch

NAMES = ["codebase-design", "diagnosing-bugs", "grilling", "resolving-merge-conflicts", "tdd"]
FOOTER = ("- **Refactoring is not part of the loop.** It belongs to the review stage "
          "(see the `code-review` skill), not the red → green implementation cycle.\n")
OLD = "cb01f66bebfaa25fa1f88e6b7e769cd9fd9f35b1120b8563749820738814c927"
CANONICAL = "15c3a204ee9e926ffe14e5e02ab06e2773bdc9507be019ad18dc38d325316ce5"


def layout(legacy=False):
    home, claude, agents, store = laptop_layout()
    for name in NAMES:
        shutil.copytree(SKILLS / name, agents / name)
        (claude / name).symlink_to("../../.agents/skills/" + name, target_is_directory=True)
    if legacy:
        with (agents / "tdd/SKILL.md").open("a") as stream:
            stream.write(FOOTER)
    return home, claude, agents, store


def tree(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def test_five_canonical_links_migrate_without_restoration():
    home, claude, agents, _ = layout()
    before = tree(agents)
    run_role(home, "install-skills", skills=NAMES, host="laptop", check=True)
    assert all((claude / name).is_symlink() for name in NAMES)
    run_role(home, "install-skills", skills=NAMES, host="laptop")
    assert all(not (claude / name).is_symlink() for name in NAMES)
    assert tree(agents) == before


def test_exact_restoration_then_five_link_migration():
    home, claude, agents, store = layout(legacy=True)
    target = agents / "tdd/SKILL.md"
    before = target.stat()
    assert len(FOOTER.encode()) == 149
    assert hashlib.sha256(target.read_bytes()).hexdigest() == OLD
    run_role(home, "restore-laptop-tdd", host="laptop", check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == OLD
    run_role(home, "restore-laptop-tdd", host="laptop")
    backup = home / ".cache/chaldea-scratch/rollout-guidance-20261018/tdd-before-canonical"
    saved = backup / "SKILL.md"
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == OLD
    assert (saved.stat().st_mode, saved.stat().st_mtime_ns) == (before.st_mode, before.st_mtime_ns)
    assert json.loads((backup / "metadata.json").read_text())["checksum"] == OLD
    assert hashlib.sha256(target.read_bytes()).hexdigest() == CANONICAL
    assert (claude / "tdd").is_symlink()
    preserved = tree(agents)
    names = ["safety-critical-code", "unslop"] + NAMES
    run_role(home, "install-skills", skills=names, host="laptop", check=True)
    assert all((claude / name).is_symlink() for name in names)
    run_role(home, "install-skills", skills=names, host="laptop")
    assert tree(agents) == preserved
    for name in names:
        assert not (claude / name).is_symlink()
        assert {k: v[0] for k, v in tree(claude / name).items()} == {
            k: v[0] for k, v in tree(SKILLS / name).items()}
    assert (store / "keep").read_text() == "unmanaged"
    assert re.search(r"changed=0\s", run_role(home, "install-skills", skills=names, host="laptop"))


@pytest.mark.parametrize("bad", ["external", "broken", "modified", "wrong-relative", "owner", "other-host", "nested-link", "ancestor-link"])
def test_new_link_refusals_preserve_every_link_and_target(bad):
    home, claude, agents, store = layout()
    if bad in ["external", "broken", "wrong-relative"]:
        link = claude / "codebase-design"
        link.unlink()
        external = scratch() / "identical-external"
        shutil.copytree(SKILLS / "codebase-design", external)
        destination = external if bad == "external" else agents / "absent" if bad == "broken" else agents / "codebase-design"
        link.symlink_to(destination, target_is_directory=True)
    elif bad == "modified":
        (agents / "tdd/SKILL.md").write_text("unapproved local content")
    elif bad == "nested-link":
        (agents / "grilling/local").symlink_to(store, target_is_directory=True)
    elif bad == "ancestor-link":
        (home / ".agents").rename(home / "actual-agents")
        (home / ".agents").symlink_to("actual-agents", target_is_directory=True)
    before = tree(agents)
    for check in [True, False]:
        run_role(home, "install-skills", skills=["safety-critical-code", "unslop"] + NAMES,
                 host="agent-a" if bad == "other-host" else "laptop",
                 uid=os.getuid() + 1 if bad == "owner" else None, check=check, succeeds=False)
        assert all((claude / name).is_symlink() for name in NAMES + ["safety-critical-code", "unslop"])
        assert tree(agents) == before
        assert (store / "keep").read_text() == "unmanaged"


def test_legacy_tdd_is_refused_without_the_separate_restoration():
    home, claude, agents, _ = layout(legacy=True)
    before = tree(agents)
    for check in [True, False]:
        run_role(home, "install-skills", skills=NAMES, host="laptop", check=check, succeeds=False)
        assert all((claude / name).is_symlink() for name in NAMES)
        assert tree(agents) == before


@pytest.mark.parametrize("bad", ["content", "backup-collision", "file-link", "other-host", "owner", "backup-parent-link"])
def test_restoration_refuses_unapproved_data_before_writing(bad):
    home, claude, agents, _ = layout(legacy=True)
    target = agents / "tdd/SKILL.md"
    folder = home / ".cache/chaldea-scratch/rollout-guidance-20261018/tdd-before-canonical"
    if bad == "content":
        target.write_text(target.read_text() + "another edit\n")
    elif bad == "backup-collision":
        folder.mkdir(parents=True)
        (folder / "keep").write_text("original backup")
    elif bad == "file-link":
        target.rename(agents / "tdd/other")
        target.symlink_to("other")
    elif bad == "backup-parent-link":
        (home / ".cache").symlink_to(scratch() / "sync-store", target_is_directory=True)
    before = tree(agents)
    run_role(home, "restore-laptop-tdd", host="agent-a" if bad == "other-host" else "laptop",
             uid=os.getuid() + 1 if bad == "owner" else None, succeeds=False)
    assert tree(agents) == before
    assert (claude / "tdd").is_symlink()
    if bad == "backup-collision":
        assert (folder / "keep").read_text() == "original backup"


@pytest.mark.parametrize("host", ["omarchy-pc", "agent-a", "agent-b"])
def test_other_hosts_remain_identical_and_idempotent(host):
    home = scratch() / "fleet"
    home.mkdir()
    run_role(home, "main", host=host)
    before = tree(home)
    assert re.search(r"changed=0\s", run_role(home, "main", host=host))
    assert tree(home) == before
    assert not (home / ".cache/chaldea-scratch").exists()
