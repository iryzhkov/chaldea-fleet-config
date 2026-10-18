#!/usr/bin/python
"""Verify an immutable Huyang release, migrate the checkout and activate atomically."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
from uuid import uuid4

from ansible.module_utils.basic import AnsibleModule

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_directory(path):
    """Refuse links in existing parents, including a dangling final link."""
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and not part.is_dir()):
            raise ValueError("managed directory has a symlink or non-directory component: " + str(part))


def inspect_archive(archive, expected_sha, version, architecture):
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise ValueError("missing inventory archive SHA-256")
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive must be a bounded regular file")
    if sha256(archive.read_bytes()) != expected_sha:
        raise ValueError("archive SHA-256 differs from inventory")
    files = {}
    with tarfile.open(archive, "r:gz") as stream:
        members = stream.getmembers()
        if sum(m.size for m in members) > MAX_ARCHIVE_BYTES or len(members) > 4096:
            raise ValueError("archive exceeds unpacked size or member limit")
        for member in members:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or str(path) != member.name or member.name in files or member.mode & 0o7000):
                raise ValueError("archive contains an unsafe or duplicate member")
            source = stream.extractfile(member)
            assert source is not None
            files[member.name] = source.read()
    manifest = json.loads(files.get("manifest.json", b""))
    if manifest.get("version") != version or manifest.get("architecture") != architecture:
        raise ValueError("manifest version or architecture differs from inventory")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or not {"bin/huyang", "lua/huyang/rpc.lua"} <= expected.keys():
        raise ValueError("manifest lacks runtime entry points")
    if set(files) != set(expected) | {"manifest.json"}:
        raise ValueError("archive members differ from manifest")
    for name, digest in expected.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest) or sha256(files[name]) != digest:
            raise ValueError("file SHA-256 differs from manifest")
    return files


def existing_release(destination, files):
    if not destination.exists():
        return False
    safe_directory(destination)
    actual = {}
    for path in destination.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("immutable release contains an unsafe entry")
        if path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o022:
            raise ValueError("immutable release has unsafe ownership or permissions")
        if path.is_file():
            actual[path.relative_to(destination).as_posix()] = path.read_bytes()
    if actual != files or not os.access(destination / "bin/huyang", os.X_OK):
        raise ValueError("immutable installed release differs; inspect drift before reinstalling")
    return True


def current_target(root):
    link = root / "current"
    if link.is_symlink():
        target = Path(os.readlink(link))
        if not target.is_absolute() or target.parent != root / "releases":
            raise ValueError("current must name a fleet release")
        return target
    if link.exists():
        raise ValueError("refusing non-link current path")
    return None


def replace_link(path, target):
    # Create the new link alongside the old one and rename across in one operation.
    stage = path.parent / (".link-" + uuid4().hex)
    try:
        stage.symlink_to(target, target_is_directory=True)
        os.replace(stage, path)
    finally:
        if stage.is_symlink():
            stage.unlink()


def install(module):
    p = module.params
    version = p["version"]
    if not re.fullmatch(r"huyang-v[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("expected huyang-vX.Y.Z")
    root = Path(p["root"])
    if not root.is_absolute():
        raise ValueError("root must be absolute")
    safe_directory(root)
    safe_directory(root / "releases")
    marker = root / "restart-required"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise ValueError("unsafe restart intent path")
    files = inspect_archive(Path(p["archive"]), p["sha256"], version, p["architecture"])
    backup = root.with_name(root.name + ".pre-fleet")
    legacy = (root / ".git").exists()
    if legacy and (backup.exists() or backup.is_symlink()):
        raise ValueError("legacy backup already exists; inspect before migrating")
    if root.exists() and not legacy and not (root / "releases").is_dir():
        raise ValueError("unrecognized Huyang layout; inspect before migrating")
    destination = root / "releases" / version
    installed = existing_release(destination, files) if not legacy else False
    target = current_target(root) if not legacy else None
    changed = not installed or legacy or (p["activate"] and target != destination)
    if module.check_mode:
        return changed
    if not installed:
        # Verify and fully stage before touching the old running checkout.
        stage = Path(tempfile.mkdtemp(prefix=".huyang-install-", dir=root.parent))
        try:
            for name, data in files.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                path.write_bytes(data)
                path.chmod(0o755 if name == "bin/huyang" else 0o644)
            for path in stage.rglob("*"):
                if path.is_dir():
                    path.chmod(0o755)
            if legacy:
                os.rename(root, backup)
            (root / "releases").mkdir(parents=True, exist_ok=True, mode=0o700)
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    if p["activate"] and target != destination:
        # Keep intent until the service restart and health checks complete. A failed
        # restart or interrupted converge is retried even after current was switched.
        marker.write_text(version + "\n")
        marker.chmod(0o600)
        if target:
            replace_link(root / "previous", target)
        replace_link(root / "current", destination)
    return changed


def main():
    module = AnsibleModule(argument_spec={
        "root": {"type": "path", "required": True},
        "archive": {"type": "path", "required": True},
        "version": {"type": "str", "required": True},
        "architecture": {"type": "str", "choices": ["x64", "arm64"], "required": True},
        "sha256": {"type": "str", "required": True},
        "activate": {"type": "bool", "default": False},
    }, supports_check_mode=True)
    try:
        module.exit_json(changed=install(module))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        module.fail_json(msg="Huyang release refused: " + str(error))


if __name__ == "__main__":
    main()
