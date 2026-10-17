"""Toolchain provisioning tests: local archives, no network or host changes."""
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tarfile
from unittest.mock import patch

import pytest
import yaml

ROLE = Path(__file__).resolve().parents[1] / "roles/chaldea_job_host"
loader = importlib.machinery.SourceFileLoader("job_toolchains", str(ROLE / "files/chaldea-job-toolchains"))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
manager = importlib.util.module_from_spec(spec)
loader.exec_module(manager)
DEFAULTS = yaml.safe_load((ROLE / "defaults/main.yml").read_text())["chaldea_job_host_toolchain_versions"]


def bundle(tool):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        names = ("uv", "uvx") if tool == "uv" else ("bin/" + tool,)
        for name in names:
            entry = tarfile.TarInfo("release/" + name)
            payload = b"#!/bin/sh\nexit 0\n"
            entry.size, entry.mode, entry.uid, entry.gid = len(payload), 0o755, 12345, 12345
            archive.addfile(entry, io.BytesIO(payload))
    return data.getvalue()


def fake_fetch(url, destination):
    tool = next(t for t in manager.TOOLS if ("/" + t in url or "/" + t + "-" in url))
    data = bundle(tool)
    name = url.split("/")[-1].removesuffix(".sha256")
    if url.endswith(".sha256") or url.endswith("SHASUMS256.txt"):
        destination.write_text(hashlib.sha256(data).hexdigest() + "  " + name + "\n")
    else:
        destination.write_bytes(data)


@pytest.mark.parametrize("tool", ["node", "go", "uv"])
def test_install_is_atomic_immutable_and_idempotent(tmp_path, tool):
    root = tmp_path / "tree"
    root.mkdir()
    # Published format differs for Node; use each release's actual filenames.
    url, sums, name = manager.release(tool, DEFAULTS[tool][0], "x86_64")[0]
    def fetch(source, destination):
        data = bundle(tool)
        if source == sums:
            destination.write_text(hashlib.sha256(data).hexdigest() + "  " + name + "\n")
        else:
            destination.write_bytes(data)
    with patch.object(manager, "fetch", side_effect=fetch) as network:
        assert manager.install(root, tool, DEFAULTS[tool][0], "x86_64")
        first_calls = network.call_count
        assert not manager.install(root, tool, DEFAULTS[tool][0], "x86_64")
        assert network.call_count == first_calls
    directory = root / tool / DEFAULTS[tool][0]
    assert (directory.stat().st_mode & 0o777) == 0o555
    assert ((directory / "bin" / tool).stat().st_mode & 0o777) == 0o555
    assert not list(root.glob(".stage-*"))
    manifest = json.loads((directory / manager.MARKER).read_text())
    assert manifest["architecture"] == "x86_64" and manifest["sha256"]


@pytest.mark.parametrize("tool", manager.TOOLS)
def test_checksum_failure_never_publishes_or_runs_installer(tmp_path, tool):
    root = tmp_path / "tree"
    root.mkdir()
    def fetch(url, destination):
        if url.endswith(".sha256") or url.endswith("SHASUMS256.txt"):
            destination.write_text("0" * 64 + "\n")
        else:
            destination.write_bytes(bundle(tool))
    with patch.object(manager, "fetch", side_effect=fetch), patch.object(manager.subprocess, "run") as run:
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            manager.install(root, tool, DEFAULTS[tool][0], "x86_64")
        run.assert_not_called()
    assert not (root / tool / DEFAULTS[tool][0]).exists()
    assert not list(root.glob(".stage-*"))


def test_rust_verifies_all_components_before_running_standalone_installers(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    events = []
    def fetch(url, destination):
        events.append("fetch")
        data = bundle("rust")
        destination.write_bytes((hashlib.sha256(data).hexdigest() + "\n").encode()
                                if url.endswith(".sha256") else data)
    def run(argv, **kwargs):
        assert events.count("fetch") == 6
        assert "--disable-ldconfig" in argv
        assert kwargs["env"]["TMPDIR"].startswith(str(root))
        assert "--prefix=" in argv[2]
        events.append("install")
    with patch.object(manager, "fetch", side_effect=fetch), patch.object(manager.subprocess, "run", side_effect=run):
        manager.install(root, "rust", "1.99.0", "x86_64")
    assert events == ["fetch"] * 6 + ["install"] * 3


def test_prune_keeps_all_configured_plus_former_default_and_is_idempotent(tmp_path):
    parent = tmp_path / "node"
    parent.mkdir()
    for version in ("20.1.0", "22.1.0", "24.1.0", "26.1.0", "26.2.0"):
        path = parent / version
        path.mkdir()
        (path / "file").write_text(version)
        manager.seal(path)
    configured = ["26.1.0", "26.2.0"]
    planned = manager.prune(tmp_path, "node", configured, previous="22.1.0", dry_run=True)
    assert len(planned) == 2 and len(list(parent.iterdir())) == 5
    assert manager.prune(tmp_path, "node", configured, previous="22.1.0") == planned
    assert {p.name for p in parent.iterdir()} == set(configured + ["22.1.0"])
    assert manager.prune(tmp_path, "node", configured, previous="22.1.0") == []


def test_plan_missing_tree_does_not_write_or_download(tmp_path):
    root = tmp_path / "absent"
    with patch.object(manager, "fetch", side_effect=AssertionError("network")):
        assert len(manager.reconcile(root, DEFAULTS, "x86_64", dry_run=True)) == 4
    assert not root.exists()


@pytest.mark.parametrize("architecture,node,go,rust", [
    ("x86_64", "x64", "amd64", "x86_64"),
    ("aarch64", "arm64", "arm64", "aarch64"),
])
def test_official_release_architecture_mapping(architecture, node, go, rust):
    manager.validate(DEFAULTS, architecture)
    assert f"linux-{node}" in manager.release("node", "26.12.0", architecture)[0][0]
    assert f"linux-{go}" in manager.release("go", "1.27.0", architecture)[0][0]
    assert rust + "-unknown-linux-gnu" in manager.release("uv", "0.12.10", architecture)[0][0]
    assert len(manager.release("rust", "1.99.0", architecture)) == 3


@pytest.mark.parametrize("version", ["stable", "../escape", "1x2x3", "1.2.3/evil"])
def test_unpinned_or_unsafe_version_refused(version):
    with pytest.raises(ValueError):
        manager.validate({**DEFAULTS, "node": [version]}, "x86_64")


def test_symlink_destination_refused(tmp_path):
    (tmp_path / "node").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        manager.install(tmp_path, "node", "26.12.0", "x86_64")


def test_wrong_existing_architecture_refused(tmp_path):
    path = tmp_path / "node/26.12.0"
    path.mkdir(parents=True)
    (path / manager.MARKER).write_text(json.dumps(
        {"tool": "node", "version": "26.12.0", "architecture": "aarch64"}))
    with pytest.raises(ValueError, match="does not match"):
        manager.install(tmp_path, "node", "26.12.0", "x86_64")


def test_archive_path_escape_refused_before_publish(tmp_path):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        entry = tarfile.TarInfo("../../escape")
        entry.size = 1
        archive.addfile(entry, io.BytesIO(b"x"))
    payload = data.getvalue()
    def fetch(url, destination):
        destination.write_bytes((hashlib.sha256(payload).hexdigest() + "\n").encode()
                                if url.endswith("SHASUMS256.txt") else payload)
    with patch.object(manager, "fetch", side_effect=fetch):
        with pytest.raises(tarfile.FilterError):
            manager.install(tmp_path, "node", "26.12.0", "x86_64")
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "node/26.12.0").exists()


def test_abandoned_staging_is_pruned_on_apply(tmp_path):
    abandoned = tmp_path / ".stage-crashed/payload"
    abandoned.mkdir(parents=True)
    (abandoned / "partial").write_text("partial")
    manager.seal(abandoned)
    with patch.object(manager, "install", return_value=False):
        changes = manager.reconcile(tmp_path, DEFAULTS, "x86_64")
    assert changes == ["remove abandoned staging " + str(abandoned.parent)]
    assert not abandoned.parent.exists()


def test_busy_job_refuses_before_install_or_prune(tmp_path):
    import fcntl
    import subprocess
    import sys
    lock = tmp_path / "admission.lock"
    with lock.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        result = subprocess.run(
            [sys.executable, "-I", str(ROLE / "files/chaldea-job-toolchains"),
             "--root", str(tmp_path / "tree"), "--versions", json.dumps(DEFAULTS),
             "--architecture", "x86_64", "--admission-lock", str(lock)],
            text=True, capture_output=True, timeout=5)
    assert result.returncode != 0
    assert "BlockingIOError" in result.stderr
    assert not (tmp_path / "tree").exists()


def test_role_installs_as_root_after_mount_and_serializes_selection():
    tasks = yaml.safe_load((ROLE / "tasks/toolchains.yml").read_text())
    install = next(t for t in tasks if "ansible.builtin.command" in t)
    assert install["become"] is True
    assert "chaldea_job_host_mount_ready.rc == 0" in install["when"]
    assert "--admission-lock" in install["ansible.builtin.command"]["argv"]
    main = (ROLE / "tasks/main.yml").read_text()
    assert main.index("Secure the mounted filesystem") < main.index("Provision pinned job toolchains")
    assert main.index("Provision pinned job toolchains") < main.index("Install the job host configuration")
