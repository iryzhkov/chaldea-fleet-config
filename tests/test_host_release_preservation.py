"""Exercise the unchanged installer plus exact additional retention through Ansible."""
import os
from pathlib import Path

import pytest

from host_artifact_fixture import stage
from test_host_artifact import run_role


FIVE = ["host-v0.2.2", "host-v0.2.1", "host-v0.1.1", "host-v0.2.4", "host-v0.2.6"]


@pytest.mark.parametrize("preserve", [False, True, "five"])
def test_default_two_or_explicit_third_release_and_cache(tmp_path, preserve):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    pins = stage(tmp_path)
    releases, cache = tmp_path / "releases", tmp_path / "cache"
    releases.mkdir()
    cache.mkdir()
    older = ["host-v0.2.2", "host-v0.2.3", "host-v0.2.1"]
    if preserve == "five":
        # Five explicit old releases plus the newest prior and the selected one.
        older += ["host-v0.1.1", "host-v0.2.4", "host-v0.2.6"]
    for version, stamp in zip(older, [100, 300, 50, 20, 150, 200]):
        path = releases / version
        path.mkdir()
        (path / "consumer").write_text(version)
        os.utime(path, (stamp, stamp))
        for suffix in (".tar.gz", ".json"):
            (cache / (version + suffix)).write_text(version)
    # Never follow a release-shaped symlink during retention.
    outside = tmp_path / "unmanaged"
    outside.mkdir()
    (outside / "keep").write_text("untouched")
    (releases / "host-v0.0.1").symlink_to(outside, target_is_directory=True)
    explicit = FIVE if preserve == "five" else ["host-v0.2.2"] if preserve else []
    if explicit:
        pins["chaldea_host_artifact_preserve_versions"] = explicit
    result = run_role(tmp_path, pins)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = {pins["chaldea_host_version"], "host-v0.2.3"} | set(explicit)
    actual = {p.name for p in releases.iterdir() if p.is_dir() and not p.is_symlink()}
    assert actual == expected
    assert len(actual) == (7 if preserve == "five" else 2 + len(explicit))
    assert {p.name for p in cache.iterdir()} == {v + suffix for v in expected for suffix in (".tar.gz", ".json")}
    for version in expected - {pins["chaldea_host_version"]}:
        assert (releases / version / "consumer").read_text() == version
        for suffix in (".tar.gz", ".json"):
            assert (cache / (version + suffix)).read_text() == version
    assert (outside / "keep").read_text() == "untouched"
    again = run_role(tmp_path, pins)
    assert again.returncode == 0 and "changed=0" in again.stdout, again.stdout + again.stderr


@pytest.mark.parametrize("invalid", ["host-v0.2.2", {}, ["/opt/host-v0.2.2"], ["../host-v0.2.2"],
    ["unknown"], [2], ["host-v0.2.2\n"], ["host-v0.2.2"] * 2,
    [f"host-v0.2.{i}" for i in range(9)]])
def test_malformed_preservation_stops_before_any_install_or_delete(tmp_path, invalid):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    pins = stage(tmp_path)
    sentinel = tmp_path / "releases/host-v0.2.2"
    sentinel.mkdir(parents=True)
    (sentinel / "consumer").write_text("keep")
    result = run_role(tmp_path, pins | dict(chaldea_host_artifact_preserve_versions=invalid))
    assert result.returncode != 0
    assert (sentinel / "consumer").read_text() == "keep"
    assert not (tmp_path / "cache").exists()
    assert "TASK [chaldea_host_artifact : Create root-owned" not in result.stdout
