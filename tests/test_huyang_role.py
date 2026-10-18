"""Exercise release/service wiring behind isolated toolchain and systemctl boundaries."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[1]
FAKE_MCP = b"""#!/usr/bin/python3
import json, sys
servers = {"go": "gopls", "rust": "rust_analyzer", "python": "pyright", "java": "jdtls",
           "typescript": "ts_ls", "javascript": "ts_ls", "cpp": "clangd", "c": "clangd", "bash": "bashls"}
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    result = {}
    if request["method"] == "tools/call":
        params = request["params"]
        language = params["arguments"]["root"].rsplit("/", 1)[-1]
        data = {"semantic_provider": {"state": "healthy"}}
        if params["name"] == "language_server_status":
            data = {"language_servers": {"languages": [{
                "filetype": "sh" if language == "bash" else language,
                "lsp": servers[language], "attach": "attached", "treesitter_parser": True}]}}
        result = {"structuredContent": {"outcome": "ok", "data": data}}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
"""


def fixture(tmp_path, monkeypatch, version="huyang-v9.0.0"):
    home = Path.home()
    assert home.is_relative_to(Path(os.environ["TMPDIR"]))
    assert tmp_path.is_relative_to(Path(os.environ["TMPDIR"]))
    assert "/tmp/" not in str(home)
    roles = tmp_path / "roles"
    if not roles.exists():
        shutil.copytree(ROOT / "roles/huyang", roles / "huyang")
        # Toolchain's checksum/real-runtime tests cover that boundary separately.
        # This fixture retains the actual installer, unit, activation and health tasks.
        (roles / "huyang/tasks/lspconfig.yml").write_text(yaml.safe_dump([{
            "name": "Expose a disposable toolchain fixture",
            "ansible.builtin.set_fact": {
                "huyang_toolchain_bin": str(home / "toolchain/bin"),
                "huyang_headless_init": str(home / "toolchain/headless-init.lua"),
                "huyang_java_home": "",
            },
        }]))
    archive = tmp_path / (version + ".tar.gz")
    files = {"bin/huyang": FAKE_MCP, "lua/huyang/rpc.lua": b"return {}\n"}
    files["manifest.json"] = json.dumps({
        "version": version, "architecture": "x64",
        "files": {path: hashlib.sha256(data).hexdigest() for path, data in files.items()},
    }).encode()
    with tarfile.open(archive, "w:gz") as stream:
        for path, data in files.items():
            member = tarfile.TarInfo(path)
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
    manager = tmp_path / "systemctl.json"
    if not manager.exists():
        manager.write_text(json.dumps({"units": {"huyang.service": {"active": True, "enabled": True}}, "calls": []}))
    monkeypatch.setenv("PATH", str(ROOT / "tests/fake-bin") + ":" + os.environ["PATH"])
    monkeypatch.setenv("FAKE_SYSTEMCTL_STATE", str(manager))
    monkeypatch.setenv("FAKE_SYSTEMCTL_UNIT_HOME", str(home))
    # A real AF_UNIX node, never a host service or socket.
    control = tmp_path / "control.sock"
    if not control.exists():
        directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with socket.socket(socket.AF_UNIX) as node:
                # A short fd path avoids Linux sockaddr_un limits while the
                # actual socket node stays in the asserted scratch directory.
                node.bind(f"/proc/self/fd/{directory}/control.sock")
        finally:
            os.close(directory)
    return {
        "fleet_home": str(home), "huyang_enabled": True, "huyang_version": version,
        "huyang_sha256": {"x86_64": hashlib.sha256(archive.read_bytes()).hexdigest()},
        "huyang_archive_source": str(archive), "huyang_socket": str(control),
        "huyang_languages": ["go", "bash"], "huyang_memory_high": "1G",
        "ansible_facts": {"architecture": "x86_64", "user_uid": os.getuid()},
        "ansible_python_interpreter": sys.executable,
    }, roles, manager


def apply(base, variables, roles, check=False, selected_role="huyang"):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]))
    play = base / "huyang.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Huyang role with an isolated user manager", "hosts": "localhost",
        "connection": "local", "gather_facts": False, "vars": variables, "roles": [selected_role],
    }]))
    return subprocess.run(["ansible-playbook", "-i", "localhost,", str(play),
                           *(["--check", "--diff"] if check else [])],
                          env=dict(os.environ, ANSIBLE_ROLES_PATH=str(roles)),
                          cwd=ROOT, text=True, capture_output=True)


def success(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_role_check_real_second_real_pin_restart_and_state_preservation(tmp_path, monkeypatch):
    variables, roles, manager = fixture(tmp_path, monkeypatch)
    home = Path.home()
    checkout = home / ".local/share/huyang"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "keep").write_bytes(b"old checkout")
    trust, state = home / ".config/huyang/config.toml", home / ".local/state/huyang/keep"
    for path in (trust, state):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"operator state")
    result = apply(tmp_path, variables, roles, check=True)
    success(result)
    assert json.loads(manager.read_text())["calls"] == []
    assert (checkout / ".git").exists() and not checkout.with_name("huyang.pre-fleet").exists()
    first = apply(tmp_path, variables, roles)
    success(first)
    assert json.loads(manager.read_text())["calls"].count(["restart", "huyang.service"]) == 1
    assert (checkout.with_name("huyang.pre-fleet") / "keep").read_bytes() == b"old checkout"
    assert all(path.read_bytes() == b"operator state" for path in (trust, state))
    unit = (home / ".config/systemd/user/huyang.service").read_text()
    assert "current/bin/huyang serve" in unit and "MemoryHigh=1G" in unit
    assert "UnsetEnvironment=HUYANG_RUNTIME_PATH AGENT99_RUNTIME_PATH" in unit
    assert (checkout / "bin/huyang").resolve() == checkout / "releases/huyang-v9.0.0/bin/huyang"
    second = apply(tmp_path, variables, roles)
    success(second)
    assert "changed=0" in second.stdout
    assert json.loads(manager.read_text())["calls"].count(["restart", "huyang.service"]) == 1
    variables, roles, manager = fixture(tmp_path, monkeypatch, version="huyang-v9.1.0")
    success(apply(tmp_path, variables, roles))
    assert json.loads(manager.read_text())["calls"].count(["restart", "huyang.service"]) == 2
    assert (checkout / "previous").resolve() == checkout / "releases/huyang-v9.0.0"


def test_check_mode_refuses_a_legacy_backup_collision_without_service_calls(tmp_path, monkeypatch):
    variables, roles, manager = fixture(tmp_path, monkeypatch)
    checkout = Path.home() / ".local/share/huyang"
    (checkout / ".git").mkdir(parents=True)
    checkout.with_name("huyang.pre-fleet").mkdir()
    result = apply(tmp_path, variables, roles, check=True)
    assert result.returncode != 0
    assert "existing pre-fleet backup" in result.stdout
    assert json.loads(manager.read_text())["calls"] == []


def test_mcp_registration_keeps_disabled_bytes_and_selects_current_when_enabled(tmp_path):
    home = Path.home()
    assert home.is_relative_to(Path(os.environ["TMPDIR"]))
    variables = {
        "fleet_home": str(home), "chaldea_node_version": "26.10.0",
        "mcp_registrations_claude": [str(ROOT / "tests/fake-claude"), str(home / "claude-mcp.json")],
    }
    for enabled in (False, True):
        variables["huyang_enabled"] = enabled
        success(apply(tmp_path, variables, ROOT / "roles", selected_role="mcp_registrations"))
        codex = tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]["huyang"]
        command = str(home / ".local/share/huyang") + ("/current" if enabled else "") + "/bin/huyang"
        assert codex["command"] == command
        assert codex["args"] == ["mcp", "--profile", "full"]
        claude = json.loads((home / "claude-mcp.json").read_text())
        assert claude["huyang"]["command"] == command
        assert claude["huyang"]["args"] == ["mcp", "--profile", "full"]
