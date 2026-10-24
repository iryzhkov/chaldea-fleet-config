"""Fixed provider profiles from the client role, applied only in scratch trees.

The protected root, owner, group and become are fixed role variables; these tests
override them with extra vars so the role writes into a scratch tree without root.
The native binary is a copy of the job host's echo, so the rendered launcher can be
executed for real and its exact argv observed. Each profile home holds a FIFO named
auth.json: any open of it would block, so a completed run proves it was never read.
"""
import grp
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from test_chaldea_client import ROOT, safe
from test_chaldea_client import run as run_role
from test_chaldea_session_policy import PRESET, SECRET, policy_variables, protected_tree

ROLE = ROOT / "roles/chaldea_client"
PROFILE = "codex-tooling-reporter"
URL = "https://jocasta.example.test/mcp"
TOOLS = ["get", "history", "list", "search"]
CONFIG = ['cli_auth_credentials_store="file"', "features.plugins=false", "features.apps=false",
          "features.multi_agent=false", "features.multi_agent_v2={enabled=false,disable_native_tools=true}",
          "features.goals=false", "features.view_image=false", "features.shell_tool=false",
          'web_search="disabled"']
REFUSED = "CODEX_PROFILE_REFUSED\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(path):
    raw = path.read_bytes()
    return {"source": str(path), "sha256": sha(raw), "size": len(raw)}


def catalog_bytes(models):
    return json.dumps({"models": models}, separators=(",", ":")).encode() + b"\n"


def layout(tmp_path, monkeypatch):
    variables = policy_variables(tmp_path, monkeypatch)
    home = Path.home()
    safe(home)
    variables["ansible_facts"] = {"user_uid": os.getuid(), "user_gid": os.getgid()}
    runtime = home / ".local/share/chaldea/releases/client-v9.0.0"
    extra = protected_tree(tmp_path) | {
        "chaldea_client_session_profile_group": grp.getgrgid(os.getgid()).gr_name,
        "chaldea_client_session_profile_owner_gid": os.getgid(),
        "chaldea_client_waits_resolved_runtime": str(runtime)}
    installs = home / ".local/share/mise/installs/codex/0.163.0/bin"
    installs.mkdir(parents=True)
    native = installs / "codex"
    native.write_bytes(Path("/usr/bin/echo").read_bytes())
    native.chmod(0o755)
    machine = int.from_bytes(native.read_bytes()[18:20], "little")
    host = installs / "codex-code-mode-host"
    host.write_bytes(b"\x7fELF\x02\x01\x01" + b"\0" * 11 + machine.to_bytes(2, "little") + b"host" * 16)
    host.chmod(0o755)
    catalog = home / ".local/share/chaldea-profile-inputs/models.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(catalog_bytes([{"slug": "fixture-model", "apply_patch_tool_type": None,
                                        "tool_mode": "code_mode_only"}]))
    catalog.chmod(0o644)
    state = home / ".local/state/chaldea/profiles" / PROFILE
    profile_home = state / "home"
    (profile_home / ".codex").mkdir(parents=True)
    profile_home.chmod(0o700)
    (profile_home / ".codex").chmod(0o700)
    os.mkfifo(profile_home / ".codex/auth.json", 0o600)
    tmpdir = state / "tmp"
    tmpdir.mkdir(mode=0o700)
    profile = {"driver": "codex", "native": pin(native), "host": pin(host), "catalog": pin(catalog),
               "elf_machine": machine, "model": "fixture-model", "home": str(profile_home),
               "tmpdir": str(tmpdir), "cwd": str(home), "preset": PRESET, "audience": "jocasta",
               "server": "jocasta_projectA", "url": URL, "tools": list(TOOLS),
               "disabled_servers": ["jocasta", "home_only"]}
    variables["chaldea_client_session_profiles"] = {PROFILE: profile}
    directory = Path(extra["chaldea_client_session_policy_path"]).parent / PROFILE
    helper = (f"{home}/.local/share/mise/installs/node/26.10.0/bin/node {runtime}/bin/chaldea session headers"
              f" --preset {PRESET} --audience jocasta --config {home}/.config/chaldea/waits.json")
    return SimpleNamespace(base=tmp_path, home=home, variables=variables, extra=extra, profile=profile,
                           native=native, host=host, catalog=catalog, profile_home=profile_home,
                           tmpdir=tmpdir, directory=directory, helper=helper,
                           config=profile_home / ".codex/config.toml",
                           protected=Path(extra["chaldea_client_session_policy_root"]))


def run(case, entry="session-profiles", check=False, variables=None):
    safe(case.base)
    play = case.base / (entry + ".yml")
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    play.write_text(yaml.safe_dump([{
        "name": "Fixed provider profiles in scratch", "hosts": "localhost", "connection": "local",
        "gather_facts": False, "vars": defaults | (variables or case.variables),
        "tasks": [{"name": "Exercise the profile entrypoint",
                   "ansible.builtin.include_role": {"name": "chaldea_client", "tasks_from": entry}}]}]))
    extra_file = case.base / "protected.json"
    extra_file.write_text(json.dumps(case.extra))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles"), ANSIBLE_NOCOLOR="1",
               ANSIBLE_LOCAL_TEMP=str(case.base / "ansible-local"),
               ANSIBLE_REMOTE_TEMP=str(case.base / "ansible-remote"))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play), "-e", "@" + str(extra_file),
                             *(["--check", "--diff"] if check else [])],
                            env=env, cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert SECRET not in result.stdout + result.stderr
    return result


def ok(result):
    assert result.returncode == 0, result.stdout[-12000:] + result.stderr[-4000:]


def launch(case, argv=("app-server",), cwd=None):
    return subprocess.run([str(case.directory / "exec"), *argv], cwd=cwd or case.home,
                          env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=60)


def expected_native(case):
    disabled = {"enabled": False, "command": "/usr/bin/false"}
    return {"mcp_servers": {"jocasta": disabled, "home_only": disabled, "jocasta_projectA": {
        "url": URL, "http_headers_helper": case.helper, "enabled_tools": TOOLS}}}


def test_off_by_default_and_wired_after_the_policy(tmp_path, monkeypatch):
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert defaults["chaldea_client_session_profiles"] == {}
    assert defaults["chaldea_client_session_profiles_absent"] == []
    fixed = yaml.safe_load((ROLE / "vars/main.yml").read_text())
    assert (fixed["chaldea_client_session_profile_group"], fixed["chaldea_client_session_profile_owner_gid"]) == ("root", 0)
    system = (ROLE / "tasks/waits-system.yml").read_text()
    assert system.index("include_tasks: session-policy.yml") < system.index("include_tasks: session-profiles.yml")
    assert "chaldea_client_session_profiles | default({}) | length > 0" in system
    assert system.index("import_tasks: session-profiles-validate.yml") < system.index("Create only private waits directories")
    main = (ROLE / "tasks/main.yml").read_text()
    assert main.index("import_tasks: session-profiles-validate.yml") < main.index("include_tasks: client.yml")
    assert main.index("waits-system.yml") < main.index("include_tasks: session-profiles-absent.yml")
    case = layout(tmp_path, monkeypatch)
    case.variables["chaldea_client_session_profiles"] = {}
    ok(run(case))
    assert not (case.protected / "etc/chaldea").exists()
    assert not case.config.exists()


def test_check_real_second_and_actual_launch(tmp_path, monkeypatch):
    case = layout(tmp_path, monkeypatch)
    ok(run(case, check=True))
    assert not (case.protected / "etc/chaldea").exists()
    assert not case.config.exists()
    real = run(case)
    ok(real)
    assert "changed=0" not in real.stdout
    for name, mode, raw in (("codex", 0o755, case.native.read_bytes()), ("codex-code-mode-host", 0o755, case.host.read_bytes()),
                            ("models.json", 0o644, case.catalog.read_bytes())):
        target = case.directory / name
        assert target.read_bytes() == raw
        st = target.lstat()
        assert (st.st_mode & 0o7777, st.st_uid, st.st_gid, st.st_nlink) == (mode, os.getuid(), os.getgid(), 1)
    assert json.loads((case.directory / "mcp.json").read_text()) == {"mcpServers": {"jocasta_projectA": {
        "type": "http", "url": URL, "headersHelper": case.helper}}}
    assert tomllib.loads(case.config.read_text()) == expected_native(case)
    assert sorted(p.name for p in case.directory.iterdir()) == [
        "codex", "codex-code-mode-host", "exec", "mcp.json", "models.json"]
    assert sorted(p.name for p in (case.profile_home / ".codex").iterdir()) == ["auth.json", "config.toml"]
    st = (case.directory / "exec").lstat()
    assert (st.st_mode & 0o7777, st.st_nlink) == (0o755, 1)
    second = run(case)
    ok(second)
    assert "changed=0" in second.stdout, second.stdout
    # The rendered launcher FD-executes the pinned echo copy with the fixed argv.
    launched = launch(case)
    assert launched.returncode == 0, launched.stderr
    argv = []
    for value in (*CONFIG, "model_catalog_json=" + json.dumps(str(case.directory / "models.json"))):
        argv += ["-c", value]
    assert launched.stdout == " ".join(argv + ["app-server", "--strict-config"]) + "\n"
    # Environment, working directory and descriptor identity, observed in process.
    launcher = runpy.run_path(str(case.directory / "exec"))
    captured = {}

    class Executed(BaseException):
        pass

    def execve(fd, args, env):
        captured.update(inode=os.fstat(fd).st_ino, args=args, env=env, cwd=os.getcwd())
        raise Executed()
    monkeypatch.chdir(case.home)
    monkeypatch.setattr(sys, "argv", ["exec", "app-server"])
    with patch.object(os, "execve", side_effect=execve), pytest.raises(Executed):
        launcher["main"]()
    assert captured["inode"] == (case.directory / "codex").stat().st_ino
    assert captured["args"][0] == str(case.directory / "codex")
    assert captured["cwd"] == str(case.profile_home)
    assert captured["env"] == {"HOME": str(case.profile_home), "CODEX_HOME": str(case.profile_home / ".codex"),
                               "TMPDIR": str(case.tmpdir), "PATH": "/usr/bin:/bin"}


def mutate_profile(change):
    def apply(case):
        change(case.profile, case)
    return apply


def repin_catalog(models):
    def apply(case):
        case.catalog.write_bytes(catalog_bytes(models))
        case.profile["catalog"] = pin(case.catalog)
    return apply


def relink(path):
    saved = path.with_name(path.name + ".saved")
    path.rename(saved)
    path.symlink_to(saved)


def policy_off(case):
    case.variables["chaldea_client_session_policy_enabled"] = False


def second_profile(case):
    case.variables["chaldea_client_session_profiles"]["other"] = dict(case.profile)


def retire_same(case):
    case.variables["chaldea_client_session_profiles_absent"] = [{"name": PROFILE, "home": case.profile["home"]}]


def protected_link(case):
    case.directory.mkdir(parents=True)
    (case.directory / "exec").symlink_to(case.native)


def hardlinked_config(case):
    case.config.write_text("")
    os.link(case.config, case.profile_home / ".codex/held")


FILTER = "Fixed provider profile refused"
REFUSALS = {
    "unknown field": (mutate_profile(lambda p, c: p.update(extra=True)), FILTER),
    "claude driver": (mutate_profile(lambda p, c: p.update(driver="claude")), FILTER),
    "undeclared preset": (mutate_profile(lambda p, c: p.update(preset="other")), FILTER),
    "model differs from preset": (mutate_profile(lambda p, c: p.update(model="other-model")), FILTER),
    "url differs from enrollment": (mutate_profile(lambda p, c: p.update(url="https://other.example.test/mcp")), FILTER),
    "ungranted tool": (mutate_profile(lambda p, c: p.update(tools=TOOLS + ["put"])), FILTER),
    "server also disabled": (mutate_profile(lambda p, c: p.update(disabled_servers=["jocasta_projectA"])), FILTER),
    "operator home": (mutate_profile(lambda p, c: p.update(home=str(c.home))), FILTER),
    "home outside fleet home": (mutate_profile(lambda p, c: p.update(home="/var/lib/profile")), FILTER),
    "dot segment": (mutate_profile(lambda p, c: p.update(home=p["home"] + "/../x")), FILTER),
    "cwd outside fleet home": (mutate_profile(lambda p, c: p.update(cwd="/srv/t3")), FILTER),
    "cwd sibling of fleet home": (mutate_profile(lambda p, c: p.update(cwd=str(c.home) + "x")), FILTER),
    "cwd alias of fleet home": (mutate_profile(lambda p, c: p.update(cwd=str(c.home) + "/.")), FILTER),
    "uppercase hash": (mutate_profile(lambda p, c: p["native"].update(sha256=p["native"]["sha256"].upper())), FILTER),
    "boolean size": (mutate_profile(lambda p, c: p["host"].update(size=True)), FILTER),
    "oversized catalog pin": (mutate_profile(lambda p, c: p["catalog"].update(size=65537)), FILTER),
    "unknown machine": (mutate_profile(lambda p, c: p.update(elf_machine=3)), FILTER),
    "shared home": (second_profile, FILTER),
    "retired and delivered": (retire_same, FILTER),
    "policy off": (policy_off, "need the protected session policy"),
    "native hash": (mutate_profile(lambda p, c: p["native"].update(sha256="0" * 64)), "pinned size"),
    "native size": (mutate_profile(lambda p, c: p["native"].update(size=p["native"]["size"] + 1)), "pinned size"),
    "native link": (lambda c: relink(c.native), "pinned size"),
    "writable host": (lambda c: c.host.chmod(0o775), "pinned size"),
    "two models": (repin_catalog([{"slug": "fixture-model", "apply_patch_tool_type": None},
                                  {"slug": "x", "apply_patch_tool_type": None}]), "only the profile model"),
    "other model": (repin_catalog([{"slug": "x", "apply_patch_tool_type": None}]), "only the profile model"),
    "patch enabled": (repin_catalog([{"slug": "fixture-model", "apply_patch_tool_type": "freeform"}]),
                      "only the profile model"),
    "patch unset": (repin_catalog([{"slug": "fixture-model"}]), "only the profile model"),
    "missing home": (lambda c: shutil.rmtree(c.profile_home), "must be an existing directory"),
    "shared home mode": (lambda c: c.profile_home.chmod(0o750), "must be an existing directory"),
    "linked home": (lambda c: relink(c.profile_home), "must be an existing directory"),
    "linked codex home": (lambda c: relink(c.profile_home / ".codex"), "must be an existing directory"),
    "hardlinked config": (hardlinked_config, "must be absent or owned"),
    "linked launcher target": (protected_link, "must be absent or owned"),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_refused_before_any_profile_write(tmp_path, monkeypatch, name):
    case = layout(tmp_path, monkeypatch)
    change, message = REFUSALS[name]
    change(case)
    result = run(case)
    assert result.returncode != 0, result.stdout
    assert message in result.stdout, result.stdout[-12000:]
    assert not (case.directory / "codex").exists()
    assert not (case.directory / "mcp.json").exists()
    if name != "hardlinked config":
        assert not case.config.exists()


@pytest.mark.parametrize("entry", ["main", "session-profiles", "session-profiles-absent"])
@pytest.mark.parametrize("check", [False, True])
def test_renamed_codex_home_collision_refused_before_mutation(tmp_path, monkeypatch, entry, check):
    case = layout(tmp_path, monkeypatch)
    old_directory = case.directory.with_name("retired-codex")
    old_directory.mkdir(parents=True)
    sentinels = {case.config: b"existing Codex config\n",
                 old_directory / "exec": b"existing launcher\n",
                 old_directory / "mcp.json": b"existing MCP config\n"}
    for path, content in sentinels.items():
        path.write_bytes(content)
    before = {path: path.stat() for path in sentinels}
    case.variables["chaldea_client_session_profiles_absent"] = [
        {"name": old_directory.name, "home": case.profile["home"]}]
    result = run(case, entry=entry, check=check)
    assert result.returncode != 0, result.stdout
    assert "delivered and retired Codex profile homes must be disjoint" in result.stdout, result.stdout[-12000:]
    assert "changed=0" in result.stdout, result.stdout
    assert not case.directory.exists()
    assert not (case.home / ".config").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]
    for path, content in sentinels.items():
        current = path.stat()
        for field in ("st_mode", "st_uid", "st_gid", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"):
            assert getattr(current, field) == getattr(before[path], field)
        assert path.read_bytes() == content
    assert (case.profile_home / ".codex/auth.json").is_fifo()


def test_launcher_refuses_drift_before_native_exec(tmp_path, monkeypatch):
    case = layout(tmp_path, monkeypatch)
    ok(run(case))
    assert launch(case).returncode == 0

    def refused(result):
        assert (result.returncode, result.stderr) == (78, REFUSED), result
        assert result.stdout == ""

    refused(launch(case, argv=("app-server", "--extra")))
    refused(launch(case, argv=()))
    refused(launch(case, cwd=case.tmpdir))
    for target, change in ((case.directory / "mcp.json", lambda raw: raw + b" "),
                           (case.config, lambda raw: raw + b"# drift\n"),
                           (case.directory / "models.json", lambda raw: raw.replace(b"code_mode_only", b"code_mode_ONLY")),
                           (case.directory / "codex", lambda raw: raw[:-1] + bytes([raw[-1] ^ 1])),
                           (case.directory / "codex-code-mode-host", lambda raw: raw[:-1] + b"x")):
        original = target.read_bytes()
        target.write_bytes(change(original))
        refused(launch(case))
        target.write_bytes(original)
    host = case.directory / "codex-code-mode-host"
    held = case.directory.parent / "held-host"
    host.rename(held)
    refused(launch(case))
    host.symlink_to(held)
    refused(launch(case))
    host.unlink()
    held.rename(host)
    case.profile_home.chmod(0o750)
    refused(launch(case))
    case.profile_home.chmod(0o700)
    case.directory.chmod(0o775)
    refused(launch(case))
    case.directory.chmod(0o755)
    os.link(case.config, case.profile_home / ".codex/held")
    refused(launch(case))
    (case.profile_home / ".codex/held").unlink()
    assert launch(case).returncode == 0
    # Complete native config equality: rebinding only the byte hash still refuses.
    launcher = runpy.run_path(str(case.directory / "exec"))
    original = case.config.read_bytes()
    for mutated in (original + b'\n[mcp_servers.unexpected]\nenabled = false\ncommand = "/usr/bin/false"\n',
                    original.replace(b"enabled = false", b"enabled = true", 1),
                    original.replace(b'command = "/usr/bin/false"', b'command = "/bin/true"', 1),
                    original.replace(b'command = "/usr/bin/false"\n', b"", 1),
                    original.replace(b'enabled_tools = [', b'enabled_tools = ["put", ', 1),
                    b'unrelated = true\n' + original):
        assert mutated != original
        case.config.write_bytes(mutated)
        with patch.dict(launcher["fixed_mcp_config"].__globals__, FILE_SHA256=sha(mutated)):
            with pytest.raises(ValueError):
                launcher["fixed_mcp_config"]()
    case.config.write_bytes(original)
    launcher["fixed_mcp_config"]()
    # Ordinary convergence repairs drift in a role-owned file.
    (case.directory / "mcp.json").write_text("{}")
    repaired = run(case)
    ok(repaired)
    assert "changed=0" not in repaired.stdout
    assert launch(case).returncode == 0


def retired(case):
    return case.variables | {"chaldea_client_session_profiles": {}, "chaldea_client_session_profiles_absent": [
        {"name": PROFILE, "home": str(case.profile_home)}]}


def test_guarded_inverse_removes_only_role_owned_files(tmp_path, monkeypatch):
    case = layout(tmp_path, monkeypatch)
    ok(run(case))
    variables = retired(case)
    ok(run(case, entry="session-profiles-absent", check=True, variables=variables))
    assert (case.directory / "exec").exists() and case.config.exists()
    removed = run(case, entry="session-profiles-absent", variables=variables)
    ok(removed)
    assert not case.directory.exists() and not case.config.exists()
    assert case.directory.parent.is_dir()
    assert sorted(p.name for p in (case.profile_home / ".codex").iterdir()) == ["auth.json"]
    assert case.native.exists() and case.catalog.exists()
    again = run(case, entry="session-profiles-absent", variables=variables)
    ok(again)
    assert "changed=0" in again.stdout, again.stdout


def test_disjoint_codex_retirement_preserves_delivered_profile(tmp_path, monkeypatch):
    old = layout(tmp_path, monkeypatch)
    ok(run(old))
    new = SimpleNamespace(**vars(old))
    new.profile_home = old.profile_home.with_name("replacement-home")
    new.tmpdir = old.tmpdir.with_name("replacement-tmp")
    new.profile_home.mkdir(mode=0o700)
    (new.profile_home / ".codex").mkdir(mode=0o700)
    os.mkfifo(new.profile_home / ".codex/auth.json", 0o600)
    new.tmpdir.mkdir(mode=0o700)
    new.config = new.profile_home / ".codex/config.toml"
    new.directory = old.directory.with_name("replacement-codex")
    new.profile = old.profile | {"home": str(new.profile_home), "tmpdir": str(new.tmpdir)}
    new.variables = old.variables | {
        "chaldea_client_session_profiles": {new.directory.name: new.profile},
        "chaldea_client_session_profiles_absent": [{"name": PROFILE, "home": str(old.profile_home)}]}
    # Exercise the delivery-then-retirement ordering of the ordinary role.
    ok(run(new))
    delivered = {path: path.read_bytes() for path in [new.config, *new.directory.iterdir()]}
    ok(run(new, entry="session-profiles-absent", check=True))
    assert old.directory.is_dir() and old.config.exists()
    ok(run(new, entry="session-profiles-absent"))
    assert not old.directory.exists() and not old.config.exists()
    assert (old.profile_home / ".codex/auth.json").is_fifo()
    assert (new.profile_home / ".codex/auth.json").is_fifo()
    assert {path: path.read_bytes() for path in delivered} == delivered
    assert launch(new).returncode == 0
    again = run(new, entry="session-profiles-absent")
    ok(again)
    assert "changed=0" in again.stdout, again.stdout


def test_inverse_refuses_foreign_paths(tmp_path, monkeypatch):
    case = layout(tmp_path, monkeypatch)
    ok(run(case))
    variables = retired(case)
    relink(case.directory / "exec")
    result = run(case, entry="session-profiles-absent", variables=variables)
    assert result.returncode != 0 and "is not a role-owned profile path" in result.stdout, result.stdout[-8000:]
    assert all((case.directory / n).exists() for n in ("exec", "codex", "mcp.json")) and case.config.exists()
    (case.directory / "exec").unlink()
    (case.directory / "exec.saved").rename(case.directory / "exec")
    relink(case.profile_home / ".codex")
    result = run(case, entry="session-profiles-absent", variables=variables)
    assert result.returncode != 0 and "is not a role-owned profile path" in result.stdout, result.stdout[-8000:]
    assert (case.directory / "exec").exists()
    (case.profile_home / ".codex").unlink()
    (case.profile_home / ".codex.saved").rename(case.profile_home / ".codex")
    foreign = case.directory / "foreign"
    foreign.write_text("not role owned")
    result = run(case, entry="session-profiles-absent", variables=variables)
    assert result.returncode != 0
    assert foreign.read_text() == "not role owned"


def test_ordinary_role_validates_profiles_before_mutation(tmp_path, monkeypatch):
    case = layout(tmp_path, monkeypatch)
    variables = case.variables | {"chaldea_client_session_policy_enabled": False,
                                  "chaldea_client_waits_service_mode": "user"}
    result = run_role(tmp_path, variables)
    assert result.returncode != 0
    assert "Fixed provider profiles need the protected session policy" in result.stdout, result.stdout[-8000:]
    assert not (case.home / ".config").exists()
    assert not json.loads((tmp_path / "systemctl.json").read_text())["calls"]
