"""Exercise only the owned OpenCode plugin seam in disposable homes."""
import os
import hashlib
import urllib.request
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PINS = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())
PLUGIN_URL = ("https://raw.githubusercontent.com/iryzhkov/omarchy-setup/"
              + PINS["agent_config_huyang_plugin_ref"]
              + "/config/opencode/plugins/huyang-profiles.js")


@pytest.fixture(scope="session")
def plugin_source(tmp_path_factory):
    path = tmp_path_factory.mktemp("plugin") / "huyang-profiles.js"
    configured = os.environ.get("HUYANG_PLUGIN_SOURCE")
    data = Path(configured).read_bytes() if configured else urllib.request.urlopen(PLUGIN_URL, timeout=30).read()
    assert hashlib.sha256(data).hexdigest() == PINS["agent_config_huyang_plugin_sha256"]
    path.write_bytes(data)
    return path


def apply_plugin(base, home, source, *, check=False):
    assert home.is_relative_to(base)
    play = base / "plugin.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Isolated OpenCode plugin fixture",
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(home),
                 "agent_config_huyang_plugin_url": source.as_uri(),
                 "agent_config_huyang_plugin_sha256": PINS["agent_config_huyang_plugin_sha256"]},
        "tasks": [{"name": "Apply only the plugin tasks", "ansible.builtin.include_role": {
            "name": "agent_config", "tasks_from": "opencode-huyang.yml",
        }}],
    }]))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
    return subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)]
                          + (["--check", "--diff"] if check else []),
                          env=env, text=True, capture_output=True)


def test_fresh_check_mode_defers_download_without_creating_destination(tmp_path, plugin_source):
    home = tmp_path / "fresh-home"
    result = apply_plugin(tmp_path, home, plugin_source, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Would install checksum-pinned OpenCode Huyang plugin" in result.stdout
    assert not home.exists()


def test_synthetic_model_switch_and_acp_contract(plugin_source):
    env = dict(os.environ, HUYANG_PLUGIN_SOURCE=str(plugin_source))
    subprocess.run(["node", "--test", str(ROOT / "tests/opencode-huyang.test.mjs")],
                   env=env, check=True)


def test_distribution_is_narrow_and_idempotent(tmp_path, plugin_source):
    home = tmp_path / "home"
    plugins = home / ".config/opencode/plugins"
    plugins.mkdir(parents=True)
    config = home / ".config/opencode/opencode.json"
    config.write_text('{"model":"keep","permission":{"edit":"ask"}}\n')
    sibling = plugins / "user.js"
    sibling.write_text("// user owned\n")
    wrapper = home / ".local/bin/opencode"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\nexit 0\n")
    before = {path: path.read_bytes() for path in (config, sibling, wrapper)}
    first = apply_plugin(tmp_path, home, plugin_source)
    assert first.returncode == 0, first.stdout + first.stderr
    target = plugins / "huyang-profiles.js"
    assert target.read_bytes() == plugin_source.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o644
    second = apply_plugin(tmp_path, home, plugin_source)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "changed=0" in second.stdout
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize("collision", ["file", "plugin_symlink", "parent_symlink", "directory"])
def test_distribution_refuses_unowned_and_unsafe_destinations(tmp_path, collision, plugin_source):
    home = tmp_path / "home"
    plugins = home / ".config/opencode/plugins"
    plugins.mkdir(parents=True)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("keep\n")
    target = plugins / "huyang-profiles.js"
    if collision == "file":
        target.write_text("// user owned\n")
    elif collision == "plugin_symlink":
        target.symlink_to(sentinel)
    elif collision == "parent_symlink":
        plugins.rmdir()
        plugins.symlink_to(outside, target_is_directory=True)
    else:
        target.mkdir()
    result = apply_plugin(tmp_path, home, plugin_source)
    assert result.returncode != 0
    assert sentinel.read_text() == "keep\n"
    if collision == "file":
        assert target.read_text() == "// user owned\n"
    elif collision == "plugin_symlink":
        assert target.is_symlink()
    elif collision == "parent_symlink":
        assert plugins.is_symlink()
    else:
        assert target.is_dir()


def test_claude_and_codex_keep_the_explicit_full_registration():
    defaults = yaml.safe_load((ROOT / "roles/mcp_registrations/defaults/main.yml").read_text())
    huyang = next(item for item in defaults["mcp_registrations_servers"] if item["name"] == "huyang")
    assert huyang["args"] == ["mcp", "--profile", "full"]
    assert defaults["mcp_registrations_providers"] == ["claude", "codex"]
