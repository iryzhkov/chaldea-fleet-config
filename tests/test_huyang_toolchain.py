"""Huyang toolchain integrity and activation contracts; remote execution only."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/huyang"
spec = importlib.util.spec_from_file_location("huyang_toolchain", ROLE / "files/huyang-toolchain.py")
assert spec and spec.loader
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)
PINS = yaml.safe_load((ROOT / "inventory/group_vars/all/huyang-toolchain.yml").read_text())["huyang_toolchain_pins"]
LANGUAGES = list(manager.SERVERS)


@pytest.fixture(autouse=True)
def require_scratch_home():
    home = Path(os.environ["HOME"]).resolve()
    temporary = Path(os.environ["TMPDIR"]).resolve()
    assert home == temporary / "fleet-test-home" or "chaldea-scratch/agent-tooling" in str(home), "tests require a scratch HOME"
    assert not str(home).startswith("/tmp/")
    assert temporary in home.parents or home in temporary.parents or "chaldea-scratch/agent-tooling" in str(temporary)


def defaults():
    values = yaml.safe_load((ROLE / "defaults/main.yml").read_text()) if (ROLE / "defaults/main.yml").exists() else {}
    extra = ROLE / "defaults/toolchain.yml"
    if extra.exists():
        values.update(yaml.safe_load(extra.read_text()))
    return values


def test_exact_nine_and_both_architectures_have_reviewed_pins():
    assert defaults()["huyang_languages"] == LANGUAGES
    assert defaults()["huyang_toolchain_servers"]["bash"]["filetype"] == "sh"
    for arch in ("x86_64", "aarch64"):
        manager.validate_pins(PINS, arch, LANGUAGES)
        assert set(PINS["architectures"][arch]) == {
            "nvim", "zig", "python", "go", "node", "rust_analyzer",
            "rustc", "cargo", "rust-std", "shellcheck", "jdk", "clangd",
        }
    assert set(manager.EXTRA_PARSERS) <= PINS["parsers"].keys()
    assert {"go", "rust", "python", "typescript", "tsx", "javascript", "java", "cpp", "c", "bash"} <= PINS["parsers"].keys()
    with pytest.raises(ValueError, match="unique languages"):
        manager.validate_pins(PINS, "x86_64", ["go", "go"])
    with pytest.raises(ValueError, match="architecture"):
        manager.validate_pins(PINS, "armv7l", ["go"])
    broken = copy.deepcopy(PINS)
    broken["architectures"]["aarch64"]["nvim"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pin"):
        manager.validate_pins(broken, "x86_64", ["go"])


class Response(io.BytesIO):
    url = "https://upstream.invalid/artifact"


def test_download_verifies_network_bytes_and_corrupt_cache(tmp_path, monkeypatch):
    expected = b"reviewed artifact bytes"
    pin = {"url": Response.url, "sha256": hashlib.sha256(expected).hexdigest()}
    cache = tmp_path / "downloads"
    replies = [b"tampered", expected, expected]
    monkeypatch.setattr(manager.urllib.request, "urlopen",
                        lambda *_a, **_kw: Response(replies.pop(0)))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        manager.fetch(pin, cache)
    assert not (cache / pin["sha256"]).exists()
    assert not list(cache.glob(".download-*"))
    path = manager.fetch(pin, cache)
    assert path.read_bytes() == expected
    path.write_bytes(b"corrupt cache")
    assert manager.fetch(pin, cache).read_bytes() == expected
    assert not replies
    # A verified cache hit must not contact the network.
    assert manager.fetch(pin, cache) == path


def tar(tmp_path, entries):
    path = tmp_path / "source.tar"
    with tarfile.open(path, "w") as source:
        for name, kind, target in entries:
            member = tarfile.TarInfo(name)
            member.mode = 0o755
            member.type = kind
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = target
                source.addfile(member)
            elif kind == tarfile.REGTYPE:
                body = b"hello"
                member.size = len(body)
                source.addfile(member, io.BytesIO(body))
            else:
                source.addfile(member)
    return path


@pytest.mark.parametrize("entries", [
    [("../escape", tarfile.REGTYPE, "")],
    [("/absolute", tarfile.REGTYPE, "")],
    [("root/link", tarfile.SYMTYPE, "../../escape")],
    [("root/link", tarfile.SYMTYPE, "/escape")],
    [("root/link", tarfile.LNKTYPE, "../escape")],
    [("root/fifo", tarfile.FIFOTYPE, "")],
    [("root/device", tarfile.CHRTYPE, "")],
    [("root/a", tarfile.REGTYPE, ""), ("root/a", tarfile.REGTYPE, "")],
    [("root/link", tarfile.SYMTYPE, "other"), ("root/link/write", tarfile.REGTYPE, "")],
])
def test_tar_refuses_unsafe_entries_before_any_extraction(tmp_path, entries):
    with pytest.raises(ValueError, match="unsafe|duplicate"):
        manager.unpack(tar(tmp_path, entries), tmp_path / "out", {"format": "tar", "strip": 1})
    assert not list((tmp_path / "out").rglob("*"))


def test_internal_symlink_and_executable_bits_survive(tmp_path):
    archive = tar(tmp_path, [
        ("root/lib/tool", tarfile.REGTYPE, ""),
        ("root/bin/tool", tarfile.SYMTYPE, "../lib/tool"),
    ])
    manager.unpack(archive, tmp_path / "out", {"format": "tar", "strip": 1})
    assert (tmp_path / "out/bin/tool").read_bytes() == b"hello"
    assert os.access(tmp_path / "out/bin/tool", os.X_OK)


@pytest.mark.parametrize("name,mode,body", [
    ("../escape", stat.S_IFREG | 0o644, b"x"),
    ("root/link", stat.S_IFLNK | 0o777, b"../../escape"),
    ("root/fifo", stat.S_IFIFO | 0o644, b""),
])
def test_zip_unsafe_names_links_and_nodes(tmp_path, name, mode, body):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as source:
        member = zipfile.ZipInfo(name)
        member.create_system = 3
        member.external_attr = mode << 16
        source.writestr(member, body)
    with pytest.raises(ValueError, match="unsafe"):
        manager.unpack(archive, tmp_path / "out", {"format": "zip", "strip": 1})


def fake_release(stage, root, pins, arch, languages, inputs):
    (stage / "bin").mkdir()
    (stage / "runtime/parser").mkdir(parents=True)
    (stage / "lspconfig/lsp").mkdir(parents=True)
    servers = {}
    for language in languages:
        config, executable, filetype = manager.SERVERS[language]
        servers[language] = dict(config=config, executable=executable, filetype=filetype)
        (stage / "bin" / executable).write_text("#!/bin/sh\nexit 0\n")
        (stage / "bin" / executable).chmod(0o755)
        (stage / "lspconfig/lsp" / (config + ".lua")).write_text("return {}\n")
    (stage / "bin/nvim").write_text("#!/bin/sh\nexit 0\n")
    (stage / "bin/nvim").chmod(0o755)
    (stage / "runtime/parser/go.so").write_bytes(b"fixture")
    (stage / "headless-init.lua").write_text("-- fixture\n")
    (stage / "config.json").write_text(json.dumps(dict(servers=servers, parsers=["go"])))


def input_files(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for name in ("huyang-toolchain-package.json", "huyang-toolchain-package-lock.json"):
        (inputs / name).write_text("{}\n")
    (inputs / "headless-init.lua").write_text("-- fixture\n")
    return inputs


@pytest.mark.parametrize("missing,reason", [
    ("bin/gopls", "manifest missing path: bin/gopls"),
    ("lspconfig/lsp/gopls.lua", "manifest missing path: lspconfig/lsp/gopls.lua"),
    ("runtime/parser/go.so", "manifest missing path: runtime/parser/go.so"),
])
def test_idempotent_activation_rechecks_missing_servers_and_preserves_current(tmp_path, monkeypatch, missing, reason):
    monkeypatch.setattr(manager, "build", fake_release)
    root, inputs = tmp_path / "toolchain", input_files(tmp_path)
    first = manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert first["changed"] is True
    target = (root / "current").resolve()
    second = manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert second == {**first, "changed": False}
    (target / missing).unlink()
    with pytest.raises(ValueError, match=reason):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert (root / "current").resolve() == target
    assert not list((root / "releases").glob(".build-*"))


def test_failed_new_release_never_switches_current(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "build", fake_release)
    root, inputs = tmp_path / "toolchain", input_files(tmp_path)
    manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    target = (root / "current").resolve()
    (inputs / "headless-init.lua").write_text("-- changed\n")

    def broken(*args):
        fake_release(*args)
        (args[0] / "bin/gopls").unlink()

    monkeypatch.setattr(manager, "build", broken)
    with pytest.raises(ValueError, match="missing executable"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert (root / "current").resolve() == target
    assert not list((root / "releases").glob(".build-*"))


def test_npm_lock_pins_every_transitive_input():
    package = json.loads((ROLE / "files/huyang-toolchain-package.json").read_text())
    lock = json.loads((ROLE / "files/huyang-toolchain-package-lock.json").read_text())
    assert lock["lockfileVersion"] == 3
    assert lock["packages"][""]["dependencies"] == package["dependencies"]
    assert len(lock["packages"]) > len(package["dependencies"])
    for name, value in lock["packages"].items():
        if name:
            assert value["integrity"].startswith("sha512-")
            assert value["resolved"].startswith("https://registry.npmjs.org/")
            assert value["version"]


def test_ansible_check_mode_creates_nothing_and_exposes_selected_interface(tmp_path):
    values = defaults()
    root = tmp_path / "must-not-exist"
    values.update(fleet_home=str(tmp_path), huyang_toolchain_root=str(root),
                  huyang_toolchain_pins=PINS, huyang_languages=["python", "bash"],
                  ansible_facts={"architecture": "x86_64"})
    play = [{
        "name": "Huyang check safety", "hosts": "localhost", "gather_facts": False,
        "vars": values,
        "tasks": [
            {"name": "Load toolchain task file", "ansible.builtin.include_tasks": str(ROLE / "tasks/lspconfig.yml")},
            {"name": "Check facts", "ansible.builtin.assert": {"that": [
                "huyang_toolchain_bin == huyang_toolchain_root ~ '/current/bin'",
                "huyang_headless_init == huyang_toolchain_root ~ '/current/headless-init.lua'",
                "huyang_java_home == ''",
                "huyang_expected_language_servers.bash.filetype == 'sh'",
                "huyang_expected_language_servers.keys() | sort == ['bash', 'python']",
                "not huyang_toolchain_changed",
            ]}},
        ],
    }]
    filename = tmp_path / "check.yml"
    filename.write_text(yaml.safe_dump(play))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local",
                             "--check", str(filename)], text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed=0" in result.stdout
    assert not root.exists()


def test_cli_check_has_no_network_or_writes(tmp_path):
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps(PINS))
    root = tmp_path / "unused"
    result = subprocess.run([sys.executable, "-I", str(ROLE / "files/huyang-toolchain.py"),
                             "--root", str(root), "--pins", str(pins),
                             "--architecture", "aarch64", "--languages", '["go"]',
                             "--inputs", str(tmp_path / "missing-inputs"), "--check"],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["would_install"] is True
    assert not root.exists()


@pytest.mark.parametrize("component", ["root", "ancestor", "releases", "downloads", "receipts", "state", "inputs"])
def test_managed_directory_symlinks_cannot_escape_toolchain(tmp_path, monkeypatch, component):
    inputs = input_files(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep"
    marker.write_text("unchanged")
    root = tmp_path / "toolchain"
    if component == "root":
        root.symlink_to(outside, target_is_directory=True)
    elif component == "ancestor":
        (tmp_path / "bridge").symlink_to(outside, target_is_directory=True)
        root = tmp_path / "bridge/toolchain"
    else:
        root.mkdir()
        (root / component).symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(manager, "build", lambda *_: pytest.fail("must reject before build"))
    with pytest.raises(ValueError, match="managed directory.*symlink"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert {p.name for p in outside.iterdir()} == {"keep"}
    assert marker.read_text() == "unchanged"


@pytest.mark.parametrize("location", ["lock", "input", "cache", "release", "current"])
def test_managed_file_release_and_cache_symlink_refusal(tmp_path, monkeypatch, location):
    root = tmp_path / "toolchain"
    inputs = input_files(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("unchanged")
    monkeypatch.setattr(manager, "build", fake_release)
    if location in ("release", "current"):
        installed = manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
        if location == "current":
            (root / "current").unlink()
            (root / "current").symlink_to(outside, target_is_directory=True)
        else:
            target = root / "releases" / installed["release"]
            target.rename(root / "saved")
            target.symlink_to(outside, target_is_directory=True)
    elif location == "lock":
        root.mkdir()
        (root / ".install.lock").symlink_to(outside / "keep")
    elif location == "input":
        (inputs / "headless-init.lua").unlink()
        (inputs / "headless-init.lua").symlink_to(outside / "keep")
    else:
        cache = tmp_path / "cache"
        cache.symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            manager.fetch({"sha256": "1" * 64, "url": "https://invalid.invalid"}, cache)
        assert list(outside.iterdir()) == [outside / "keep"]
        return
    with pytest.raises(ValueError, match="symlink|regular file"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    assert {p.name for p in outside.iterdir()} == {"keep"}
    assert (outside / "keep").read_text() == "unchanged"


@pytest.mark.parametrize("damage", ["binary", "parser", "config", "addition", "mode", "symlink", "receipt", "receipt-mode"])
def test_drift_refuses_before_running_any_installed_binary(tmp_path, monkeypatch, damage):
    inputs, root = input_files(tmp_path), tmp_path / "toolchain"
    monkeypatch.setattr(manager, "build", fake_release)
    manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    target = (root / "current").resolve()
    if damage == "binary":
        (target / "bin/nvim").write_text("#!/bin/sh\nexit 42\n")
    elif damage == "parser":
        (target / "runtime/parser/go.so").write_bytes(b"tampered")
    elif damage == "config":
        (target / "config.json").write_text("{}")
    elif damage == "addition":
        (target / "lspconfig/lsp/extra.lua").write_text("error('unlisted code')")
    elif damage == "mode":
        (target / "bin/gopls").chmod(0o700)
    elif damage == "symlink":
        (target / "bin/gopls").unlink()
        (target / "bin/gopls").symlink_to("/usr/bin/true")
    elif damage == "receipt":
        (target / "receipt.json").write_text("{}")
    else:
        (target / "receipt.json").chmod(0o644)
    monkeypatch.setattr(manager, "run", lambda *_: pytest.fail("executed code before checking manifest"))
    with pytest.raises(ValueError, match="manifest|installed symlink|receipt"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)


def test_internal_link_drift_and_authoritative_receipt_are_checked(tmp_path, monkeypatch):
    inputs, root = input_files(tmp_path), tmp_path / "toolchain"
    monkeypatch.setattr(manager, "build", fake_release)
    result = manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    target = (root / "current").resolve()
    (target / "bin/gopls").unlink()
    (target / "bin/gopls").symlink_to("nvim")
    # Both destinations are safe internal executables; changing the pinned
    # relationship still counts as drift.
    monkeypatch.setattr(manager, "run", lambda *_: pytest.fail("must reject before execution"))
    with pytest.raises(ValueError, match="manifest hash/type/mode"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
    authority = root / "receipts" / (result["release"] + ".json")
    baseline = json.loads(authority.read_text())
    baseline["files"] = manager.installed_manifest(target)
    authority.write_bytes(manager.receipt_bytes(baseline))
    # Editing the independent baseline alone cannot authenticate a changed release.
    with pytest.raises(ValueError, match="receipt hash mismatch"):
        manager.install_toolchain(root, PINS, "x86_64", ["go"], inputs)
