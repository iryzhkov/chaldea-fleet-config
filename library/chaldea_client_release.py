#!/usr/bin/python
"""Verify every archive member before atomically installing an immutable client."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile

from ansible.module_utils.basic import AnsibleModule


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install(module):
    p = module.params
    version = p["version"]
    if not re.fullmatch(r"client-v[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("expected client-vX.Y.Z")
    root = Path(p["root"])
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("release root must be an absolute directory, not a symlink")
    archive, manifest_path = Path(p["archive"]), Path(p["manifest"])
    if any(path.is_symlink() or not path.is_file() for path in (archive, manifest_path)):
        raise ValueError("archive and manifest must be regular files")
    if digest(archive) != p["sha256"]:
        raise ValueError("archive SHA-256 differs from inventory")
    manifest = json.loads(manifest_path.read_text())
    if manifest["version"] != version or manifest["sha256"] != p["sha256"]:
        raise ValueError("manifest version or SHA-256 differs from inventory")
    expected = manifest["files"]
    if not isinstance(expected, dict) or not {"bin/chaldea", "src/cli.ts", "package.json"} <= expected.keys():
        raise ValueError("manifest is missing client entry points")
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(set(names)) != len(names) or set(names) != set(expected):
            raise ValueError("archive members differ from manifest")
        for m in members:
            name = PurePosixPath(m.name)
            if (not m.isfile() or name.is_absolute() or ".." in name.parts
                    or str(name) != m.name or m.mode & 0o7000):
                raise ValueError("archive contains unsafe member")
            if hashlib.sha256(tar.extractfile(m).read()).hexdigest() != expected[m.name]:
                raise ValueError("archive file SHA-256 differs from manifest")
        destination = root / version
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError("installed release must be a real directory")
            actual = {}
            for path in [destination, *destination.rglob("*")]:
                if path.is_symlink():
                    raise ValueError("installed release contains a symlink")
                stat = path.stat()
                if stat.st_uid != os.geteuid() or stat.st_mode & 0o022:
                    raise ValueError("installed release has unsafe ownership or write permissions")
                if path.is_file():
                    actual[path.relative_to(destination).as_posix()] = digest(path)
            if actual != expected:
                raise ValueError("immutable installed release differs from manifest; inspect drift before reinstalling")
            return False
        if module.check_mode:
            return True
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        stage = Path(tempfile.mkdtemp(prefix=".install-", dir=root))
        try:
            # Only verified regular files. No archive path, link, owner or mode is trusted.
            for member in members:
                target = stage / member.name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                with target.open("xb") as stream:
                    shutil.copyfileobj(tar.extractfile(member), stream)
                target.chmod(0o755 if member.name.startswith("bin/") else 0o644)
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return True


def main():
    module = AnsibleModule(argument_spec={
        "root": {"type": "path", "required": True},
        "archive": {"type": "path", "required": True},
        "manifest": {"type": "path", "required": True},
        "version": {"type": "str", "required": True},
        "sha256": {"type": "str", "required": True},
    }, supports_check_mode=True)
    try:
        module.exit_json(changed=install(module))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        module.fail_json(msg="Client release refused: " + str(error))


if __name__ == "__main__":
    main()
