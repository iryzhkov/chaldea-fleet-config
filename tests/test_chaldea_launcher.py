"""The installed launcher uses the pinned Node and preserves CLI arguments."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "roles/chaldea_job_client/templates/chaldea.j2"
NODE_VERSION = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())["chaldea_node_version"]


def invoke(home, *args):
    launcher = home / "launcher"
    launcher.write_text(Environment(undefined=StrictUndefined).from_string(LAUNCHER.read_text()).render(
        chaldea_node_version=NODE_VERSION))
    return subprocess.run(["sh", str(launcher), *args], env={**os.environ, "HOME": str(home)},
                          capture_output=True, text=True)


def test_launcher_explains_a_missing_app_checkout(tmp_path):
    result = invoke(tmp_path, "exec", "--host", "agent-a", "--", "true")
    assert result.returncode == 69
    assert "app checkout is missing" in result.stderr
    assert str(tmp_path / ".local/share/chaldea/app") in result.stderr


def test_launcher_explains_a_missing_pinned_node(tmp_path):
    entry = tmp_path / ".local/share/chaldea/app/bin/chaldea"
    entry.parent.mkdir(parents=True)
    entry.write_text("fixture")
    result = invoke(tmp_path, "wait", "--help")
    assert result.returncode == 69
    assert f"pinned Node {NODE_VERSION} is missing" in result.stderr


@pytest.mark.parametrize("args", [
    ["exec", "--host", "agent-a", "--", "printf", "two words", "$HOME", ""],
    ["wait", "time", "--after", "30s", "--thread", "thread:fixture"],
    ["decision", "ask", "--question", "Run this step?", "--option", "Defer"],
])
def test_launcher_uses_bin_dispatcher_and_preserves_status_and_arguments(tmp_path, args):
    entry = tmp_path / ".local/share/chaldea/app/bin/chaldea"
    entry.parent.mkdir(parents=True)
    entry.write_text("fixture")
    node = tmp_path / f".local/share/mise/installs/node/{NODE_VERSION}/bin/node"
    node.parent.mkdir(parents=True)
    node.write_text(f"#!{sys.executable}\nimport json, sys\n"
                    "print(json.dumps(sys.argv[1:]))\n"
                    "sys.stderr.write('fixture stderr\\n')\n"
                    "sys.exit(23)\n")
    node.chmod(0o755)

    result = invoke(tmp_path, *args)

    assert result.returncode == 23
    assert json.loads(result.stdout) == [str(entry), *args]
    assert result.stderr == "fixture stderr\n"
