"""Behaviour of roles/mcp_registrations/library/mcp_registration.py."""

import importlib.util
import json
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mcp_registration", ROOT / "roles/mcp_registrations/library/mcp_registration.py")
assert spec is not None and spec.loader is not None
module_code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module_code)
FAKE_CLAUDE = str(ROOT / "tests/fake-claude")


class Exit(Exception):
    pass


class Failed(Exception):
    pass


class FakeModule:
    def __init__(self, check_mode=False):
        self.check_mode = check_mode
        self.warnings = []

    def run_command(self, argv):
        result = subprocess.run(argv, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def exit_json(self, **result):
        raise Exit(result)

    def fail_json(self, **result):
        raise Failed(result["msg"])

    def warn(self, message):
        self.warnings.append(message)


def call(provider, check_mode=False, **params):
    defaults = {"state": "present", "transport": "stdio", "command": None, "args": [], "env": {}, "url": None,
                "extra": {}, "claude_command": ["claude"], "claude_config": None, "codex_config": None}
    params = {**defaults, **params}
    module = FakeModule(check_mode)
    with pytest.raises(Exit) as done:
        module_code.check_transport(module, params)
        getattr(module_code, provider)(module, params)
    return done.value.args[0]


CODEX_CONFIG = """\
# Personal settings stay as they are.
model = "gpt-6"

[features]
hooks = true  # keep this comment

[mcp_servers.other]
command = "/usr/bin/other"
env = { TOKEN = "do-not-print" }

[mcp_servers.ov-memory]
command = "/old/ov-memory"

[mcp_servers.ov-memory.env]
OV_AGENT = "stale"

[mcp_servers.local-file-llm]
command = "/usr/bin/node"

[projects."/home/user"]
trust_level = "trusted"
"""

OV_MEMORY = {"name": "ov-memory", "command": "/home/user/.local/bin/ov-memory-mcp", "env": {"OV_AGENT": "codex-host", "OV_BASE_URL": "https://ov.example"}, "extra": {"default_tools_approval_mode": "approve", "env_vars": ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]}}

CLAUDE_OV_MEMORY = {**OV_MEMORY, "extra": {}}


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CODEX_CONFIG)
    return path


def test_codex_rewrites_only_its_own_table(config):
    result = call("codex", codex_config=str(config), **OV_MEMORY)

    text = config.read_text()
    document = tomllib.loads(text)
    assert result["changed"]
    assert document["mcp_servers"]["ov-memory"] == {"command": OV_MEMORY["command"], "args": [], "env": OV_MEMORY["env"], "default_tools_approval_mode": "approve", "env_vars": ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]}
    assert not call("codex", codex_config=str(config), **OV_MEMORY)["changed"]
    assert "hooks = true  # keep this comment\n" in text
    assert "# Personal settings stay as they are.\n" in text
    assert document["mcp_servers"]["other"]["env"]["TOKEN"] == "do-not-print"
    assert document["projects"] == {"/home/user": {"trust_level": "trusted"}}
    assert "stale" not in text


def test_codex_is_idempotent(config):
    call("codex", codex_config=str(config), **OV_MEMORY)
    before = config.read_text()

    assert not call("codex", codex_config=str(config), **OV_MEMORY)["changed"]
    assert config.read_text() == before


def test_codex_removes_a_retired_server(config):
    result = call("codex", codex_config=str(config), name="local-file-llm", state="absent")

    assert result["changed"]
    assert "local-file-llm" not in tomllib.loads(config.read_text())["mcp_servers"]
    assert not call("codex", codex_config=str(config), name="local-file-llm", state="absent")["changed"]


def test_codex_check_mode_writes_nothing_and_diffs_hide_env_values(config):
    result = call("codex", check_mode=True, codex_config=str(config), **OV_MEMORY)

    assert result["changed"]
    assert config.read_text() == CODEX_CONFIG
    shown = json.dumps(result["diff"])
    assert "OV_AGENT" in shown and "codex-host" not in shown and "stale" not in shown
    assert '"OV_AGENT": "<redacted, changed>"' in result["diff"]["after"]


def test_codex_refuses_a_definition_outside_its_own_table(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[mcp_servers]\nov-memory = { command = "/old" }\n')

    with pytest.raises(Failed, match="outside its own table"):
        call("codex", codex_config=str(path), **OV_MEMORY)
    assert path.read_text() == '[mcp_servers]\nov-memory = { command = "/old" }\n'


def test_codex_creates_a_missing_config(tmp_path):
    path = tmp_path / "codex" / "config.toml"

    call("codex", codex_config=str(path), **OV_MEMORY)

    assert tomllib.loads(path.read_text())["mcp_servers"]["ov-memory"]["command"] == OV_MEMORY["command"]
    assert path.stat().st_mode & 0o777 == 0o600


def test_claude_registers_replaces_and_removes_through_the_cli(tmp_path):
    state = tmp_path / "claude.json"
    state.write_text(json.dumps({"ov-memory": {"type": "stdio", "command": "/old", "args": [], "env": {"OV_AGENT": "stale"}}, "local-file-llm": {"type": "stdio", "command": "/usr/bin/node", "args": []}}))
    cli = [FAKE_CLAUDE, str(state)]
    huyang = {"name": "huyang", "command": "/opt/huyang", "args": ["mcp", "--profile", "full"], "extra": {"alwaysLoad": True}}

    assert call("claude", claude_command=cli, **huyang)["changed"]
    assert call("claude", claude_command=cli, **CLAUDE_OV_MEMORY)["changed"]
    assert call("claude", claude_command=cli, name="local-file-llm", state="absent")["changed"]

    servers = json.loads(state.read_text())
    assert servers == {
        "huyang": {"type": "stdio", "command": "/opt/huyang", "args": ["mcp", "--profile", "full"], "env": {}, "alwaysLoad": True},
        "ov-memory": {"type": "stdio", "command": OV_MEMORY["command"], "args": [], "env": OV_MEMORY["env"]},
    }
    assert not call("claude", claude_command=cli, **huyang)["changed"]
    assert not call("claude", claude_command=cli, **CLAUDE_OV_MEMORY)["changed"]
    assert not call("claude", claude_command=cli, name="local-file-llm", state="absent")["changed"]


def test_claude_check_mode_changes_nothing(tmp_path):
    state = tmp_path / "claude.json"
    state.write_text("{}")

    result = call("claude", check_mode=True, claude_command=[FAKE_CLAUDE, str(state)], **OV_MEMORY)

    assert result["changed"]
    assert state.read_text() == "{}"
    assert "codex-host" not in json.dumps(result["diff"])


def test_parse_claude_get_reads_the_cli_output():
    text = """\
ov-memory:
  Scope: User config (available in all your projects)
  Status: ✔ Connected
  Type: stdio
  Command: /home/user/.local/bin/ov-memory-mcp
  Args:
  Environment:
    OV_AGENT=claude-host
    OV_BASE_URL=https://ov.example

To remove this server, run: claude mcp remove ov-memory -s user
"""

    assert module_code.parse_claude_get(text) == {
        "scope": "User config (available in all your projects)",
        "type": "stdio",
        "command": "/home/user/.local/bin/ov-memory-mcp",
        "args": "",
        "env": {"OV_AGENT": "claude-host", "OV_BASE_URL": "https://ov.example"},
    }
