"""Policy/security unit tests complement the rootless real-SSH test in chaldea."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import pytest

PATH = Path(__file__).resolve().parents[1] / "roles/chaldea_job_host/files/chaldea-job-server"
loader = importlib.machinery.SourceFileLoader("job_server", str(PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
server = importlib.util.module_from_spec(spec)
loader.exec_module(server)


def request(**overrides):
    return {"version": 1, "jobId": "11111111-1111-1111-1111-111111111111",
            "argv": ["printf", "$HOME"], "cwd": "", "gpu": False,
            "artifacts": [], "files": [], **overrides}


@pytest.mark.parametrize("path", ["../x", "/x", "a//x", ".git/config", ".chaldea/log", "a/./b", "a\\b", ""])
def test_unsafe_paths(path):
    with pytest.raises(ValueError):
        server.safe_path(path)


def test_protocol_and_command_validation():
    assert server.validate(request())["argv"] == ["printf", "$HOME"]
    for override in [{"version": 2}, {"jobId": "../x"}, {"argv": "sh"},
                     {"argv": []}, {"gpu": "yes"}, {"artifacts": ["out", "out"]},
                     {"files": [{"path": "x", "size": 65 * 1024 ** 2,
                                 "sha256": "a" * 64, "mode": 0o644}]}]:
        with pytest.raises(ValueError):
            server.validate(request(**override))


def test_idle_policy_fails_closed_and_always_hosts_skip_probes():
    server.idle_policy({"policy": "always"})
    config = {"policy": "idle", "desktop_user": "igor",
              "idle_allowed_processes": ["Hyprland", "waybar"]}
    def responses(locked="yes", processes="Hyprland\nwaybar\n"):
        return [json.dumps([{"session": "1"}]).encode(),
                "Name=igor\nType=wayland\nLockedHint=" + locked + "\n",
                processes]
    with patch.object(server.subprocess, "check_output", side_effect=responses()):
        server.idle_policy(config)
    for values in [responses("no"), responses(processes="Hyprland\nsunshine\n"),
                   responses(processes="Hyprland\nunknown-game\n"), [b"[]"]]:
        with patch.object(server.subprocess, "check_output", side_effect=values):
            with pytest.raises(ValueError):
                server.idle_policy(config)
    # Even accidentally allowlisting a launcher never admits it.
    with patch.object(server.subprocess, "check_output", side_effect=responses(processes="steam\n")):
        with pytest.raises(ValueError):
            server.idle_policy({**config, "idle_allowed_processes": ["steam"]})


def test_admission_and_stale_workspace_cleanup():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace = root / request()["jobId"]
        workspace.mkdir()
        (workspace / "old").write_text("old")
        (root / "admission.lock").touch()
        server.cleanup(root)
        assert [p.name for p in root.iterdir()] == ["admission.lock"]
        with pytest.raises(ValueError, match="over cap"):
            server.admission(root, {"state_cap_bytes": 1})
        with pytest.raises(ValueError, match="disk full"):
            server.admission(root, {"min_free_bytes": 2 ** 63})


def test_sandbox_is_allowlisted_no_gpu_without_explicit_request():
    with tempfile.TemporaryDirectory() as tmp:
        cmd, env = server.sandbox(request(), Path(tmp), {"gpu_devices": ["/dev/nvidia0"]})
        assert "--unshare-all" in cmd and "--share-net" in cmd
        assert "--die-with-parent" in cmd and "--cap-drop" in cmd
        assert "--dev-bind" not in cmd
        assert not any(key in env for key in ("SSH_AUTH_SOCK", "DBUS_SESSION_BUS_ADDRESS", "GH_TOKEN"))
        assert env["HOME"] == "/home/job"
        assert cmd[-2:] == ["printf", "$HOME"]
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="GPU unavailable"):
            server.sandbox(request(gpu=True), Path(tmp), {})


def test_artifact_symlink_and_fifo_rejected_without_blocking():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "escape").symlink_to("/etc/passwd")
        with pytest.raises(ValueError, match="symlinks"):
            server.artifact_file(root, "escape")
        import os
        os.mkfifo(root / "pipe")
        with pytest.raises(ValueError, match="regular"):
            server.artifact_file(root, "pipe")
