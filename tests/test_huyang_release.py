"""Adversarial release verification and migration in disposable homes."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tarfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("huyang_release", ROOT / "roles/huyang/library/huyang_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
HEALTH_SPEC = importlib.util.spec_from_file_location("huyang_health", ROOT / "roles/huyang/files/huyang_health.py")
health = importlib.util.module_from_spec(HEALTH_SPEC)
HEALTH_SPEC.loader.exec_module(health)


def archive(base, version="huyang-v1.0.0", *, extra=None, mutate=None):
    files = {"bin/huyang": b"#!/bin/sh\nexit 0\n", "lua/huyang/rpc.lua": b"return {}\n"}
    manifest = {"version": version, "architecture": "x64",
                "files": {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}}
    files["manifest.json"] = json.dumps(manifest).encode()
    if mutate:
        mutate(files)
    path = base / (version + ".tar.gz")
    with tarfile.open(path, "w:gz") as stream:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.mode = 0o755 if name.startswith("bin/") else 0o644
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
        if extra:
            stream.addfile(extra, io.BytesIO(b"bad") if extra.isfile() else None)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def module(base, version="huyang-v1.0.0", check=False, activate=True, **kwargs):
    assert Path.home().is_relative_to(base.parent)
    path, digest = archive(base, version, **kwargs)
    return SimpleNamespace(check_mode=check, params={
        "root": str(base / "share/huyang"), "archive": str(path),
        "version": version, "sha256": digest, "architecture": "x64", "activate": activate,
    })


def test_checkout_migration_atomic_activation_rollback_and_idempotence(tmp_path):
    m = module(tmp_path)
    root = Path(m.params["root"])
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "old-binary").write_bytes(b"keep checkout")
    home = Path.home()
    state, trust = home / ".local/state/huyang/state", home / ".config/huyang/config.toml"
    for path in (state, trust):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"never change")
    assert release.install(m)
    assert (root.with_name("huyang.pre-fleet") / "old-binary").read_bytes() == b"keep checkout"
    assert (root / "current").resolve() == root / "releases/huyang-v1.0.0"
    assert (root / "restart-required").read_text() == "huyang-v1.0.0\n"
    (root / "restart-required").unlink()  # successful restart + health acknowledgement
    assert release.install(m) is False
    assert not (root / "restart-required").exists()
    second = module(tmp_path, "huyang-v1.1.0")
    assert release.install(second)
    assert (root / "previous").resolve() == root / "releases/huyang-v1.0.0"
    assert (root / "releases/huyang-v1.0.0/bin/huyang").exists()
    assert release.install(m)  # rollback uses the earlier exact pin
    assert (root / "previous").resolve() == root / "releases/huyang-v1.1.0"
    assert all(path.read_bytes() == b"never change" for path in (state, trust))


def test_check_mode_never_installs_moves_or_switches(tmp_path):
    m = module(tmp_path, check=True)
    assert release.install(m)
    assert not Path(m.params["root"]).exists()
    root = Path(m.params["root"])
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    assert release.install(m)
    assert (root / ".git").is_dir()
    assert not root.with_name("huyang.pre-fleet").exists()


@pytest.mark.parametrize("bad", ["sha", "file_hash", "manifest", "architecture", "traversal", "link", "duplicate"])
def test_archive_refusal_leaves_checkout_untouched(tmp_path, bad):
    extra = None
    mutate = None
    if bad == "traversal":
        extra = tarfile.TarInfo("../escaped")
        extra.size = 3
    elif bad == "link":
        extra = tarfile.TarInfo("escape")
        extra.type = tarfile.SYMTYPE
        extra.linkname = "../escaped"
    elif bad == "duplicate":
        extra = tarfile.TarInfo("bin/huyang")
        extra.size = 3
    elif bad == "file_hash":
        mutate = lambda files: files.update({"bin/huyang": b"tampered"})
    elif bad == "manifest":
        mutate = lambda files: files.update({"unexpected": b"extra"})
    m = module(tmp_path, extra=extra, mutate=mutate)
    if bad == "sha":
        m.params["sha256"] = "0" * 64
    elif bad == "architecture":
        m.params["architecture"] = "arm64"
    root = Path(m.params["root"])
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    with pytest.raises(ValueError):
        release.install(m)
    assert (root / ".git").is_dir()
    assert not root.with_name("huyang.pre-fleet").exists()
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("bad", ["backup", "layout", "release_link", "intent_link", "current_file", "drift"])
def test_refuse_unsafe_or_drifted_installs(tmp_path, bad):
    m = module(tmp_path)
    root = Path(m.params["root"])
    root.mkdir(parents=True)
    if bad == "backup":
        (root / ".git").mkdir()
        root.with_name("huyang.pre-fleet").mkdir()
    elif bad == "layout":
        (root / "unknown").touch()
    else:
        (root / "releases").mkdir()
        if bad == "release_link":
            (root / "releases").rmdir()
            (root / "releases").symlink_to(tmp_path)
        elif bad == "intent_link":
            (root / "restart-required").symlink_to(tmp_path / "sentinel")
        elif bad == "current_file":
            (root / "current").touch()
        else:
            release.install(m)
            (root / "current/bin/huyang").write_bytes(b"drift")
    with pytest.raises(ValueError):
        release.install(m)


@pytest.mark.parametrize("attach,lsp", [
    ("attached", "gopls"), ("starting", "starting (gopls)"),
    ("not_started", "none (configured: gopls, did not attach)"),
])
def test_presence_tolerates_attachment_latency(attach, lsp):
    reply = {"data": {"language_servers": {"languages": [
        {"filetype": "go", "attach": attach, "lsp": lsp}]}}}
    assert health.presence("go", reply)["server"] == "gopls"


def test_presence_fails_a_missing_required_server_but_not_unrelated_languages():
    with pytest.raises(ValueError, match="missing required server"):
        health.presence("go", {"data": {"language_servers": {"languages": [
            {"filetype": "go", "attach": "unconfigured", "lsp": "none"}]}}})
    assert health.presence("bash", {"data": {"language_servers": {"languages": [
        {"filetype": "sh", "attach": "attached", "lsp": "bashls"},
        {"filetype": "lua", "attach": "unconfigured", "lsp": "none"}]}}})["server"] == "bashls"


def test_every_real_host_is_disabled_and_has_a_memory_budget():
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert set(hosts) == {"agent-a", "agent-b", "omarchy-pc", "laptop"}
    assert all(host["huyang_enabled"] is False and host["huyang_memory_high"] for host in hosts.values())
    tasks = yaml.safe_load((ROOT / "roles/huyang/tasks/main.yml").read_text())
    installation = next(task for task in tasks if "block" in task)
    assert installation["when"] == "not ansible_check_mode"
    restarts = [task for task in installation["block"] if "systemd_service" in str(task)]
    assert all("systemd_service" in str(task) for task in restarts)
