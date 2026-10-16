"""Behaviour of roles/retention/files/chaldea-retention against throwaway trees."""

import importlib.machinery
import importlib.util
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "roles/retention/files/chaldea-retention"
DAY = 86400


def load_script():
    loader = importlib.machinery.SourceFileLoader("chaldea_retention", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


retention = load_script()


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def age(path, days):
    stamp = time.time() - days * DAY
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            os.utime(os.path.join(dirpath, name), (stamp, stamp), follow_symlinks=False)
    os.utime(path, (stamp, stamp))


@pytest.fixture(autouse=True)
def git_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")


@pytest.fixture
def repo(tmp_path):
    main = tmp_path / "repo"
    main.mkdir()
    git("init", "-q", "-b", "main", cwd=main)
    (main / "README").write_text("x\n")
    git("add", "README", cwd=main)
    git("commit", "-q", "-m", "init", cwd=main)
    return main


def add_worktree(repo, root, name, days, detached=False):
    path = root / "project" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if detached:
        git("worktree", "add", "-q", "--detach", str(path), cwd=repo)
    else:
        git("worktree", "add", "-q", "-b", name, str(path), cwd=repo)
    age(path, days)
    return path


def run(root, *extra):
    args = retention.parse_args(["--worktree-root", str(root), *extra])
    return retention.prune_worktrees(root, args, set(), time.time())


def test_removes_only_clean_worktrees_untouched_past_the_age_limit(repo, tmp_path):
    root = tmp_path / "worktrees"
    old = add_worktree(repo, root, "old", days=20)
    recent = add_worktree(repo, root, "recent", days=0.5)
    dirty = add_worktree(repo, root, "dirty", days=20)
    (dirty / "README").write_text("changed\n")
    age(dirty, 20)

    assert run(root) == 0

    assert not old.exists()
    assert recent.exists() and dirty.exists()


def test_dry_run_changes_nothing(repo, tmp_path):
    root = tmp_path / "worktrees"
    old = add_worktree(repo, root, "old", days=20)

    run(root, "--dry-run")

    assert old.exists()


def test_keeps_worktrees_a_process_holds(repo, tmp_path):
    root = tmp_path / "worktrees"
    held = add_worktree(repo, root, "held", days=20)
    args = retention.parse_args(["--worktree-root", str(root)])

    retention.prune_worktrees(root, args, {str(held.resolve() / "README")}, time.time())

    assert held.exists()


def test_keeps_detached_commits_that_no_branch_contains(repo, tmp_path):
    root = tmp_path / "worktrees"
    detached = add_worktree(repo, root, "detached", days=20, detached=True)
    (detached / "new").write_text("y\n")
    git("add", "new", cwd=detached)
    git("commit", "-q", "-m", "orphan", cwd=detached)
    age(detached, 20)

    run(root)

    assert detached.exists()


def test_budget_pressure_lowers_the_age_limit_but_not_the_protection_window(repo, tmp_path):
    root = tmp_path / "worktrees"
    five_days = add_worktree(repo, root, "five-days", days=5)
    today = add_worktree(repo, root, "today", days=0.5)

    assert run(root) == 0
    assert five_days.exists()

    status = run(root, "--worktree-budget-gb", "0")

    assert not five_days.exists()
    assert today.exists()
    assert status == 1


def test_tmp_removes_old_entries_and_keeps_recent_ones(tmp_path):
    tmp = tmp_path / "tmp"
    (tmp / "old").mkdir(parents=True)
    (tmp / "old" / "f").write_text("x")
    (tmp / "new").write_text("x")
    age(tmp / "old", 10)
    args = retention.parse_args(["--tmp-dir", str(tmp)])

    retention.prune_tmp(tmp, args, set(), time.time())

    assert not (tmp / "old").exists()
    assert (tmp / "new").exists()
