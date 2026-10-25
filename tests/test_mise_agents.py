"""Exercise mise ownership through Ansible and the actual compatible mise CLI."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MISE = shutil.which("mise")
GLOBAL = '''# Personal config, never rewritten.
[tools]
claude = "2.1.97"
codex = {version = "0.163.0", minimum_release_age = "48h"}
"npm:@opencode/cli" = {version = "latest", allow_builds = "@opencode/cli"}
node = ["24", "26"]
[env]
PRIVATE_FIXTURE = "do-not-print-this-value"
[settings]
experimental = true
'''
STALE = '[tools]\nclaude = "latest"\ncodex = "latest"\n"npm:@opencode/cli" = "latest"\n'


def fixture(tmp_path, global_text=GLOBAL, tools=None, install=True):
    assert MISE, "mise must be staged on PATH for the real-parser regression"
    home = Path.home()
    assert home.is_relative_to(tmp_path.parent)
    config = home / ".config/mise"
    config.mkdir(parents=True)
    global_path = config / "config.toml"
    global_path.write_text(global_text)
    dropin = config / "conf.d/agents.toml"
    dropin.parent.mkdir()
    dropin.write_text(STALE)
    record = tmp_path / "calls.jsonl"
    fake = tmp_path / "bin"
    fake.mkdir()
    installs = tmp_path / "installs"
    executable = fake / "mise"
    executable.write_text(f"""#!{sys.executable}
import json, os, pathlib, re, sys
if sys.argv[1] == 'registry':
    os.execv({MISE!r}, [{MISE!r}, *sys.argv[1:]])
with open({str(record)!r}, 'a') as stream:
    stream.write(json.dumps([sys.argv[1:], os.environ.get('MISE_MINIMUM_RELEASE_AGE')]) + '\\n')
if sys.argv[1] == 'latest':
    print('9.8.7')
elif sys.argv[1] == 'install':
    name = sys.argv[2].split('[')[0]
    if '[' not in sys.argv[2]:
        name = name.rsplit('@', 1)[0]
    name = name.replace(':', '-').replace('@', '').replace('/', '-')
    (pathlib.Path({str(installs)!r}) / name / '9.8.7').mkdir(parents=True)
else:
    raise SystemExit('unexpected mise invocation')
""")
    executable.chmod(0o755)
    variables = {"ansible_connection": "local", "ansible_python_interpreter": sys.executable,
                 "fleet_home": str(home), "mise_agents_install": install,
                 "mise_agents_installs": str(installs), "mise_agents_minimum_release_age": "36h"}
    if tools is not None:
        variables["mise_agents_tools"] = tools
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{"name": "Test mise ownership", "hosts": "localhost",
                                    "gather_facts": False, "vars": variables,
                                    "roles": ["mise_agents"]}]))
    environment = {**os.environ, "PATH": str(fake) + os.pathsep + os.environ["PATH"],
                   "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                   "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible")}

    def run(check=False, success=True):
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play),
                                 *(["--check", "--diff"] if check else [])],
                                cwd=ROOT, env=environment, capture_output=True, text=True)
        output = result.stdout + result.stderr
        assert (result.returncode == 0) == success, output
        assert "do-not-print-this-value" not in output, output
        return output

    def calls():
        return [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []

    return home, global_path, dropin, run, calls


def mise(home, *args):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("MISE_")}
    environment.update(HOME=str(home), MISE_SYSTEM_CONFIG_DIR=str(home / "empty-system"),
                       MISE_CEILING_PATHS=str(home), MISE_YES="1")
    return subprocess.run([MISE, *args], cwd=home, env=environment, text=True, capture_output=True)


def test_real_duplicate_pattern_converges_without_touching_global(tmp_path):
    home, user, managed, run, calls = fixture(tmp_path)
    before = user.read_bytes()
    failure = mise(home, "use", "--global", "--dry-run", "codex@0.163.0")
    assert failure.returncode == 1, failure.stderr
    assert "declared in multiple global config files" in failure.stderr
    selected = mise(home, "ls", "--current", "--json", "codex")
    assert selected.returncode == 0, selected.stderr
    assert json.loads(selected.stdout)[0]["source"]["path"] == str(user)
    assert json.loads(selected.stdout)[0]["requested_version"] == "0.163.0"

    stale = managed.read_bytes()
    run(check=True)
    assert managed.read_bytes() == stale
    assert not calls()
    run()
    assert user.read_bytes() == before
    assert tomllib.loads(managed.read_text())["tools"] == {}
    assert not calls()
    result = mise(home, "use", "--global", "--dry-run", "codex@0.163.0")
    assert result.returncode == 0, result.stderr
    assert user.read_bytes() == before
    assert re.search(r"changed=0\s", run())


@pytest.mark.parametrize("name", ["codex", "npm:@openai/codex", "aqua:openai/codex"])
def test_registry_equivalents_and_options_belong_to_user(tmp_path, name):
    _, user, managed, run, calls = fixture(
        tmp_path, f'[tools]\n"{name}" = {{version = "0.163.0", minimum_release_age = "48h"}}\n',
        [{"name": "codex"}])
    before = user.read_bytes()
    run()
    assert user.read_bytes() == before
    assert tomllib.loads(managed.read_text())["tools"] == {}
    assert calls() == []


def test_remaining_custom_tools_install_with_age_and_options_and_converge(tmp_path):
    _, user, managed, run, calls = fixture(
        tmp_path, '[tools]\n"claude-code" = "2.1.97"\n',
        [{"name": "claude"}, {"name": "codex"},
         {"name": "npm:fixture-tool", "install_options": "allow_builds=fixture-tool"}])
    before = user.read_bytes()
    run(check=True)
    assert not calls()
    run()
    assert tomllib.loads(managed.read_text())["tools"] == {
        "codex": "latest", "npm:fixture-tool": "latest"}
    assert calls() == [
        [["latest", "codex"], "36h"], [["latest", "npm:fixture-tool"], "36h"],
        [["install", "codex@9.8.7"], None],
        [["install", "npm:fixture-tool[allow_builds=fixture-tool]@9.8.7"], None]]
    assert re.search(r"changed=0\s", run())
    assert user.read_bytes() == before


def test_empty_selection_removes_stale_declarations_without_mise(tmp_path):
    _, user, managed, run, calls = fixture(tmp_path, tools=[])
    before = user.read_bytes()
    run()
    assert user.read_bytes() == before
    assert tomllib.loads(managed.read_text())["tools"] == {}
    assert calls() == []
    assert re.search(r"changed=0\s", run())


def test_fresh_check_mode_never_creates_files_or_runs_release_commands(tmp_path):
    _, user, managed, run, calls = fixture(tmp_path, "")
    managed.unlink()
    managed.parent.rmdir()
    user.unlink()
    user.parent.rmdir()
    run(check=True)
    assert not managed.exists()
    assert not user.exists()
    assert not calls()


def test_install_disabled_still_converges_declarations(tmp_path):
    _, _, managed, run, calls = fixture(tmp_path, "", install=False)
    run()
    assert set(tomllib.loads(managed.read_text())["tools"]) == {
        "claude", "codex", "npm:@opencode/cli"}
    assert calls() == []


@pytest.mark.parametrize("text", [
    '[env]\nSECRET = "do-not-print-this-value"\nbroken = [\n',
    '[tools]\ncodex = "1"\ncodex = "2"\n',
    '[tool_alias.custom]\nbackend = "npm:fixture"\n',
    'include = ["other.toml"]\n',
    '[tools]\nunknown-custom-plugin = "latest"\n',
    '[tools]\ncodex = 123\n',
])
def test_ambiguous_or_invalid_config_fails_before_overwrite_or_install(tmp_path, text):
    _, user, managed, run, calls = fixture(tmp_path, text)
    before = user.read_bytes(), managed.read_bytes()
    run(success=False)
    assert (user.read_bytes(), managed.read_bytes()) == before
    assert calls() == []


def test_user_fragment_also_owns_tools(tmp_path):
    _, _, managed, run, calls = fixture(tmp_path, "")
    (managed.parent / "personal.toml").write_text(GLOBAL)
    run()
    assert tomllib.loads(managed.read_text())["tools"] == {}
    assert not calls()


@pytest.mark.parametrize("unsafe", ["symlink", "directory", "managed-env", "parent-symlink"])
def test_unsafe_paths_fail_before_overwrite(tmp_path, unsafe):
    _, user, managed, run, calls = fixture(tmp_path)
    if unsafe == "symlink":
        user.rename(user.with_suffix(".saved"))
        user.symlink_to(user.with_suffix(".saved"))
    elif unsafe == "directory":
        (managed.parent / "personal").mkdir()
    elif unsafe == "parent-symlink":
        managed.parent.rename(managed.parent.with_name("conf.d-saved"))
        managed.parent.symlink_to(managed.parent.with_name("conf.d-saved"))
    else:
        managed.write_text('[env]\nPRIVATE_FIXTURE = "do-not-print-this-value"\n')
    before = managed.read_bytes()
    run(success=False)
    assert managed.read_bytes() == before
    assert not calls()
