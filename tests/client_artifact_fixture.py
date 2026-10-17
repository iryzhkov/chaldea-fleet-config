"""Public minimal client archive for activated full-site CI; no live state."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile


def stage(base):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    version = "client-v9.8.7"
    files = {"bin/chaldea": b"#!/usr/bin/env node\n", "src/cli.ts": b"// fixture\n",
             "package.json": b'{"type":"module"}\n'}
    archive = base / "chaldea-client.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = base / "manifest.json"
    manifest.write_text(json.dumps({"version": version, "sha256": checksum,
                                   "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}))
    return {"chaldea_client_enabled": True, "chaldea_client_version": version,
            "chaldea_client_sha256": checksum, "chaldea_client_archive_source": str(archive),
            "chaldea_client_manifest_source": str(manifest)}


if __name__ == "__main__":
    import os
    scratch = Path(os.environ["TMPDIR"]).resolve()
    assert Path.home().is_relative_to(scratch), "assert scratch HOME before writing"
    destination = Path(sys.argv[1]).resolve()
    assert destination.is_relative_to(scratch)
    print(json.dumps(stage(destination)))
