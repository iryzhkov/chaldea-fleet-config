"""Exercise the T3 Antigravity profile MCP link without a live T3 service."""
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_profiles_link_missing_or_empty_configs_only(tmp_path):
    home = tmp_path / "home"
    fleet = home / ".gemini/config/mcp_config.json"
    fleet.parent.mkdir(parents=True)
    fleet.write_text('{"mcpServers": {"huyang": {}}}\n')
    providers = home / ".t3/userdata/providers/antigravity"
    empty, missing, own = (providers / name / "config" for name in ("empty", "missing", "own"))
    for directory in (empty, missing, own):
        directory.mkdir(parents=True)
    (empty / "mcp_config.json").write_text("")
    (own / "mcp_config.json").write_text('{"mcpServers": {"mine": {}}}\n')
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"t3_home": str(home / ".t3"), "t3_antigravity_mcp_config": str(fleet)},
        "tasks": [{"name": "Link profiles",
                   "ansible.builtin.include_tasks": str(ROOT / "roles/t3/tasks/antigravity-mcp.yml")}],
    }]))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"))
    assert Path(env["HOME"]) == home and home.is_relative_to(tmp_path)

    def run(check=False):
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
            + (["--check"] if check else []),
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    run(check=True)
    assert not (missing / "mcp_config.json").exists()
    assert not (empty / "mcp_config.json").is_symlink()
    run()
    for directory in (empty, missing):
        link = directory / "mcp_config.json"
        assert link.is_symlink() and os.readlink(link) == str(fleet)
    assert not (own / "mcp_config.json").is_symlink()
    assert (own / "mcp_config.json").read_text() == '{"mcpServers": {"mine": {}}}\n'
    assert fleet.read_text() == '{"mcpServers": {"huyang": {}}}\n'
    assert "changed=0" in run()


def test_missing_provider_directory_is_a_no_op(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"t3_home": str(home / ".t3"),
                 "t3_antigravity_mcp_config": str(home / ".gemini/config/mcp_config.json")},
        "tasks": [{"name": "Link profiles",
                   "ansible.builtin.include_tasks": str(ROOT / "roles/t3/tasks/antigravity-mcp.yml")}],
    }]))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"))
    assert Path(env["HOME"]) == home and home.is_relative_to(tmp_path)
    result = subprocess.run(
        ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed=0" in result.stdout
    assert not (home / ".t3").exists()
