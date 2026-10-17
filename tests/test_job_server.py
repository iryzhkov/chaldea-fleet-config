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


def test_idle_policy_steam_wrapper_children_minecraft_and_custom_patterns():
    config = {"policy": "idle", "desktop_user": "igor"}
    idle = [(1, 0, "sunshine", "/usr/bin/sunshine"),
            (2, 0, "steam", "/usr/bin/steam"),
            (3, 0, "java", "java -jar ordinary-build-tool.jar")]
    assert not server.gaming(config, idle)
    cases = [
        idle + [(10, 2, "reaper", "/steam/reaper SteamLaunch AppId=570 -- game"),
                (11, 10, "game", "./game"), (12, 11, "worker", "./worker")],
        idle + [(10, 0, "java", "java net.minecraft.client.main.Main")],
        idle + [(10, 0, "java", "java net.fabricmc.loader.impl.launch.knot.KnotClient")],
        idle + [(10, 0, "java", "java -jar client.jar --gameDir /home/igor/.minecraft-modded")],
    ]
    for rows in cases:
        assert server.gaming(config, rows)
        with patch.object(server, "process_table", return_value=rows):
            with pytest.raises(server.Refused, match="Steam game or Minecraft"):
                server.idle_policy(config)
    with patch.object(server, "process_table", return_value=idle):
        server.idle_policy(config)
        server.idle_policy({"policy": "always"})
    assert server.gaming({**config, "steam_game_pattern": "custom-game"},
                         [(1, 0, "custom", "custom-game")])
    with patch.object(server.subprocess, "check_output", return_value="10 2 reaper reaper SteamLaunch AppId=42 -- game\n"):
        assert server.process_table("igor") == [(10, 2, "reaper", "reaper SteamLaunch AppId=42 -- game")]


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
            server.admission(root, {"state_cap_bytes": 1, "require_mount": False})
        with pytest.raises(ValueError, match="image full"):
            server.admission(root, {"min_free_bytes": 2 ** 63, "require_mount": False})


def test_sandbox_is_allowlisted_no_gpu_without_explicit_request():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(server.subprocess, "check_output", return_value="--disable-userns"):
            cmd, env = server.sandbox(request(), Path(tmp), {"gpu_devices": ["/dev/nvidia0"]})
        assert "--disable-userns" in cmd
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

def test_absent_mount_refuses_before_using_underlying_host_disk():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(server.Refused, match="image is not mounted"):
            server.admission(Path(tmp), {})


def test_deep_tree_over_path_max_and_unremovable_leftover_do_not_wedge_jobs(capsys):
    import os
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tree = root / "old"
        tree.mkdir()
        fd = os.open(tree, os.O_RDONLY | os.O_DIRECTORY)
        try:
            name = "d" * 200
            for _ in range(30):
                os.mkdir(name, dir_fd=fd)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = child
            file = os.open("file", os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=fd)
            os.close(file)
        finally:
            os.close(fd)
        server.remove_tree(tree)
        assert not tree.exists()  # deepest pathname exceeded 6000 bytes
        tree.mkdir()
        with patch.object(server, "remove_tree", side_effect=PermissionError):
            server.cleanup(root)
        assert "could not remove" in capsys.readouterr().err
        server.admission(root, {"require_mount": False})
        server.cleanup(root)


def test_preemption_sends_term_then_kill_after_ten_seconds_and_keeps_stdin_after_pipes_close():
    import io
    import signal
    from types import SimpleNamespace
    clock = [0.0]
    class Selector:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def register(self, *args): pass
        def unregister(self, *args): pass
        def select(self, timeout):
            clock[0] += timeout
            return []
    process = SimpleNamespace(pid=4321, stdout=io.BytesIO(), stderr=io.BytesIO(), wait=lambda **_: 0)
    signals = []
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "work"
        workspace.mkdir()
        with patch.object(server, "sandbox", return_value=(["true"], {})), \
             patch.object(server, "host_addresses", return_value=[]), \
             patch.object(server.subprocess, "Popen", return_value=process), \
             patch.object(server.os, "pidfd_open", return_value=999), \
             patch.object(server.os, "close"), \
             patch.object(server, "kill_group"), \
             patch.object(server, "job_signal", side_effect=lambda _, sig: signals.append((sig, clock[0]))), \
             patch.object(server, "gaming", return_value=True), \
             patch.object(server.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(server.selectors, "DefaultSelector", Selector):
            with pytest.raises(server.Preempted):
                server.execute(request(), workspace, {"policy": "idle"})
    assert signals[0] == (signal.SIGTERM, 5)
    assert signals[1] == (signal.SIGKILL, 15)


def test_stdin_is_monitored_after_both_output_pipes_close():
    import io
    from types import SimpleNamespace
    clock = [0.0]
    phase = [0]
    class Selector:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def register(self, *args): pass
        def unregister(self, *args): pass
        def select(self, _):
            clock[0] += .01
            phase[0] += 1
            if phase[0] == 1:
                return [(SimpleNamespace(data=k, fd=i, fileobj=i), 1) for k, i in [("O", 101), ("S", 102)]]
            return [(SimpleNamespace(data="input", fd=0), 1)]
    process = SimpleNamespace(pid=4321, stdout=io.BytesIO(), stderr=io.BytesIO(), wait=lambda **_: 0)
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "work"
        workspace.mkdir()
        with patch.object(server, "sandbox", return_value=(["true"], {})), \
             patch.object(server, "host_addresses", return_value=[]), \
             patch.object(server.subprocess, "Popen", return_value=process), \
             patch.object(server.os, "pidfd_open", return_value=999), \
             patch.object(server.os, "read", return_value=b""), \
             patch.object(server.os, "close"), \
             patch.object(server, "kill_group"), patch.object(server, "job_signal"), \
             patch.object(server.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(server.selectors, "DefaultSelector", Selector):
            with pytest.raises(ConnectionError, match="disconnected"):
                server.execute(request(), workspace, {})


def test_rendered_role_boot_limits_mixed_case_deny_and_rollback():
    import yaml
    from jinja2 import Environment, Template
    from ansible.plugins.test.core import TestModule
    role = PATH.parents[1]
    tasks = yaml.safe_load((role / "tasks/main.yml").read_text())
    guarded = next(t for t in tasks if "block" in t and "rollback" in t["name"])
    check = next(t for t in guarded["block"] if "failed_when" in t)
    env = Environment()
    env.tests.update(TestModule().tests())
    for output in ("DenyUsers chaldea-job\n", "denyusers chaldea-job\n", "DENYUSERS other chaldea-job\n"):
        value = env.from_string("{{ " + check["failed_when"] + " }}").render(
            chaldea_job_host_effective_sshd={"stdout": output})
        assert value == "False"
    assert guarded["rescue"][0]["ansible.builtin.file"]["state"] == "absent"
    defaults = yaml.safe_load((role / "defaults/main.yml").read_text())
    defaults.update(chaldea_job_host_state_root="/home/chaldea-job/jobs",
                    chaldea_job_host_image="/home/chaldea-job-state.ext4",
                    chaldea_job_host_sshd_binary="/usr/bin/sshd")
    mount = Template((role / "templates/chaldea-job.mount.j2").read_text()).render(**defaults)
    unit = Template((role / "templates/chaldea-job-sshd.service.j2").read_text()).render(**defaults)
    assert "DefaultDependencies=no" in mount and "nofail" in mount and "TimeoutSec=5" in mount
    assert "ConditionPathExists=" in mount and "WantedBy=multi-user.target" in mount
    assert "Requires=" not in mount and "Before=multi-user.target" not in mount
    assert ".mount" not in unit and "Requires=" not in unit
    assert "MemoryMax=4G" in unit and "TasksMax=256" in unit
    assert "CPUWeight=10" in unit and "IOWeight=10" in unit
    assert "state: started" in (role / "tasks/main.yml").read_text()


def test_fixed_image_creation_is_atomic_and_never_reformats_existing():
    import os
    image_loader = importlib.machinery.SourceFileLoader("image", str(PATH.with_name("chaldea-job-image")))
    image_spec = importlib.util.spec_from_loader(image_loader.name, image_loader)
    image_module = importlib.util.module_from_spec(image_spec)
    image_loader.exec_module(image_module)
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "jobs.ext4"
        assert image_module.create(image, 512 * 1024**2, (os.getuid(), os.getgid()))
        assert not image_module.create(image, 512 * 1024**2, (os.getuid(), os.getgid()))
        assert image.stat().st_size == 512 * 1024**2
        kind = server.subprocess.check_output(["blkid", "-p", "-s", "TYPE", "-o", "value", str(image)], text=True)
        assert kind.strip() == "ext4"
        with pytest.raises(ValueError, match="refusing"):
            image_module.create(image, 1024 * 1024**2, (os.getuid(), os.getgid()))
        assert not Path(str(image) + ".new").exists()
