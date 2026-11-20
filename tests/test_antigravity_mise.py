"""Antigravity participates in mise ownership and shell update policy."""
import re
import tomllib

from test_mise_agents import fixture


def test_antigravity_user_pin_is_omitted_and_shell_policy_converges(tmp_path):
    home, user, managed, run, calls = fixture(
        tmp_path, '[tools]\nantigravity-cli = "1.4.12"\n',
        tools=[{"name": "antigravity-cli"}])
    before = user.read_bytes()
    run(check=True)
    assert not (home / ".bashrc").exists()
    run()
    assert user.read_bytes() == before
    assert tomllib.loads(managed.read_text())["tools"] == {}
    assert not calls()
    for name in (".bashrc", ".zshrc"):
        assert "export AGY_CLI_DISABLE_AUTO_UPDATE=true" in (home / name).read_text()
    assert re.search(r"changed=0\s", run())


def test_antigravity_fleet_install(tmp_path):
    _, _, managed, run, calls = fixture(
        tmp_path, "", tools=[{"name": "antigravity-cli"}])
    run()
    assert tomllib.loads(managed.read_text())["tools"] == {"antigravity-cli": "latest"}
    assert calls() == [[["latest", "antigravity-cli"], "36h"],
                       [["install", "antigravity-cli@9.8.7"], None]]
