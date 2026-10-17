"""Synthetic release inputs for role tests; no production code or host services."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

PROGRAMS = (
    "chaldea-job-server", "chaldea-job-image", "chaldea-job-toolchains",
    "chaldea-retention", "chaldea-timer-report", "chaldea_outcome.py",
    "chaldea-access-trust-fetch", "exec-protocol.json",
    "access-maintenance.mjs", "akasha-collector.mjs",
)


def stage(base):
    base = Path(base).resolve()
    scratch = Path(os.environ["TMPDIR"]).resolve()
    assert Path.home().resolve().is_relative_to(scratch), "HOME must be inside the intended scratch"
    assert base.is_relative_to(scratch), "fixture output must stay inside scratch"
    base.mkdir(parents=True, exist_ok=True)
    archive = base / "chaldea-host.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in PROGRAMS:
            data = (json.dumps({"version": 1}) + "\n" if name.endswith(".json")
                    else "# synthetic release payload: " + name + "\n").encode()
            entry = tarfile.TarInfo("host/" + name)
            entry.mode = 0o644 if name.endswith((".json", ".py", ".mjs")) else 0o755
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
    manifest = base / "manifest.json"
    version = "host-v0.0.0-test"
    candidate_archive = os.environ.get("CHALDEA_HOST_TEST_ARCHIVE")
    candidate_manifest = os.environ.get("CHALDEA_HOST_TEST_MANIFEST")
    assert bool(candidate_archive) == bool(candidate_manifest), "provide both candidate release inputs"
    if candidate_archive:
        archive.write_bytes(Path(candidate_archive).read_bytes())
        manifest.write_bytes(Path(candidate_manifest).read_bytes())
        release = json.loads(manifest.read_text())
        version = release["version"]
        assert release["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if not candidate_manifest:
        manifest.write_text(json.dumps({"version": version, "sha256": digest}))
    return {
        "chaldea_host_version": version,
        "chaldea_host_sha256": digest,
        "chaldea_host_artifact_archive_source": str(archive),
        "chaldea_host_artifact_manifest_source": str(manifest),
        "chaldea_host_artifact_release_root": str(base / "releases"),
        "chaldea_host_artifact_cache": str(base / "cache"),
        "chaldea_host_artifact_become": False,
        "chaldea_host_artifact_owner": str(os.getuid()),
        "chaldea_host_artifact_group": str(os.getgid()),
        "chaldea_node_version": "26.10.0",
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(stage(Path(sys.argv[1]))))
