"""Helper packaging, identity and exact sudo admission in isolated scratch."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import types

from ansible.plugins.filter.core import FilterModule
from jinja2 import Environment, StrictUndefined
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_token_helper"


def render(name, variables):
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    env.filters.update(FilterModule().filters())
    return env.from_string((ROLE / "templates" / name).read_text()).render(variables)


def test_helper_disabled_everywhere_and_trust_enrolled_only_on_agent_a():
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    hosts = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert defaults["chaldea_token_helper_enabled"] is False
    assert defaults["chaldea_token_helper_grants"] == []
    assert defaults["chaldea_token_helper_client_sha256"] == ""
    assert defaults["chaldea_token_helper_issuer"]["uid"] == 995
    assert hosts["agent-a"]["chaldea_access_trust_enabled"] is True
    assert all(not h.get("chaldea_access_trust_enabled", False) for name, h in hosts.items() if name != "agent-a")
    assert all(not h.get("chaldea_token_helper_enabled", False) for h in hosts.values())


def test_templates_bind_config_and_allow_only_exact_selectors(tmp_path):
    assert Path(os.environ["HOME"]).is_relative_to(Path(os.environ["TMPDIR"]).parent)
    grant = dict(uid=1000, audience="akasha", action="append", source="timer",
                 host="agent-b", kind="timer_run", profile="timer-service", project="chaldea")
    identity = dict(uid=1234, key_file="/private/b.pem", name="chaldea:agent-b", kid="b-key")
    variables = dict(chaldea_token_helper_issuer=identity, chaldea_token_helper_state="/private/state",
                     chaldea_access_paths=dict(bundle="/public/bundle", root="/etc/trust", clock_health="/public/clock"),
                     chaldea_token_helper_grants=[grant],
                     chaldea_token_helper_node="/opt/helper/node/bin/node",
                     chaldea_token_helper_release="/opt/helper/releases/client-v0.2.1")
    config = json.loads(render("token-helper.json.j2", variables))
    assert config["issuer"] == identity and config["grants"] == [grant]
    assert config["anchor_file"] == "/etc/trust/anchors.json"
    sudoers = render("sudoers.j2", variables)
    assert "NOPASSWD: NOSETENV:" in sudoers
    assert "#1000 ALL=(chaldea-issuer)" in sudoers
    assert "--audience akasha --action append --source timer --host agent-b --kind timer_run" in sudoers
    assert "*" not in sudoers and "/bin/sh" not in sudoers and "/bin/node" not in sudoers
    path = tmp_path / "sudoers"
    path.write_text(sudoers)
    visudo = shutil.which("visudo") or ("/usr/sbin/visudo" if Path("/usr/sbin/visudo").exists() else None)
    assert visudo, "visudo is required to validate the privileged sudo boundary"
    subprocess.run([visudo, "-cf", str(path)], check=True, capture_output=True)
    wrapper = render("issuer-command.j2", variables)
    assert '/usr/bin/env -i PATH=/usr/bin:/bin SUDO_UID="${SUDO_UID-}"' in wrapper
    assert "/opt/helper/node/bin/node /opt/helper/releases/client-v0.2.1/bin/chaldea access token-helper" in wrapper
    assert '".local/share' not in wrapper


def test_issuer_wrapper_discards_caller_environment(tmp_path):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).parent)
    node = tmp_path / "node"
    node.write_text("#!/usr/bin/python3\nimport json,os,sys\nprint(json.dumps([dict(os.environ),sys.argv[1:]]))\n")
    node.chmod(0o700)
    wrapper = tmp_path / "issuer"
    wrapper.write_text(render("issuer-command.j2", dict(
        chaldea_token_helper_node=str(node), chaldea_token_helper_release="/opt/helper/release")))
    wrapper.chmod(0o700)
    result = subprocess.run([str(wrapper), "--source", "timer"], check=True, capture_output=True, text=True,
                            env={"SUDO_UID": "1000", "NODE_OPTIONS": "poison", "HOME": "poison", "PATH": "/poison"})
    environment, argv = json.loads(result.stdout)
    assert environment["SUDO_UID"] == "1000" and environment["PATH"] == "/usr/bin:/bin"
    assert "NODE_OPTIONS" not in environment and "HOME" not in environment
    assert argv == ["/opt/helper/release/bin/chaldea", "access", "token-helper", "--source", "timer"]


@pytest.mark.parametrize("change", [{"source": "timer*"}, {"kind": "a,b"}, {"host": "other"},
                                     {"source": "bad\nroot ALL"}, {"kind": "timer_run\n"}, {"uid": "1000"},
                                     {"client_version": "client-v0.2.0"}, {"client_version": "client-v0.2.1\n"}])
def test_inventory_injection_is_rejected_before_any_install(tmp_path, change):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).parent)
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all/main.yml").read_text())
    grant = dict(uid=1000, audience="akasha", action="append", source="timer",
                 host="localhost", kind="timer_run", profile="timer-service", project="chaldea")
    grant.update({key: value for key, value in change.items() if key != "client_version"})
    variables = inventory | yaml.safe_load((ROLE / "defaults/main.yml").read_text()) | {
        "chaldea_token_helper_enabled": True, "chaldea_access_trust_enabled": True,
        "chaldea_token_helper_client_version": change.get("client_version", "client-v0.2.1"),
        "chaldea_token_helper_client_sha256": "a" * 64,
        "chaldea_token_helper_issuer": dict(uid=995, key_file="/private/key", name="chaldea:localhost", kid="key"),
        "chaldea_token_helper_grants": [grant],
        "ansible_facts": {"architecture": "x86_64"},
    }
    play = tmp_path / "invalid.yml"
    play.write_text(yaml.safe_dump([dict(name="Reject malformed inventory", hosts="localhost",
                                        connection="local", gather_facts=False, vars=variables,
                                        roles=[str(ROLE)])]))
    environment = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"),
                       ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"),
                       ANSIBLE_LIBRARY=str(ROOT / "library"))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play), "--check"],
                            env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    expected = "Validate helper enrollment" if "client_version" in change else "Validate every exact sudo selector"
    assert expected in result.stdout
    assert "Inspect fixed launcher ancestors" not in result.stdout


def test_shared_verifier_checks_archive_before_install_and_rejects_drift(tmp_path):
    spec = importlib.util.spec_from_file_location("release", ROOT / "library/chaldea_client_release.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import io
    files = {"bin/chaldea": b"client", "bin/chaldea-token-helper": b"helper",
             "src/cli.ts": b"source", "package.json": b"{}",
             "node_modules/pkg/deep/index.js": b"dependency"}
    archive = tmp_path / "client.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(version="client-v0.2.1", sha256=sha,
                                       files={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})))
    params = dict(root=str(tmp_path / "root"), archive=str(archive), manifest=str(manifest),
                  version="client-v0.2.1", sha256="0" * 64, check_permissions=True)
    request = types.SimpleNamespace(params=params, check_mode=False)
    with pytest.raises(ValueError, match="SHA-256"):
        module.install(request)
    assert not Path(params["root"]).exists()
    params["sha256"] = sha
    previous_umask = os.umask(0o002)
    try:
        assert module.install(request)
    finally:
        os.umask(previous_umask)
    assert not module.install(request)
    installed = Path(params["root"]) / params["version"]
    assert (installed / "bin/chaldea-token-helper").stat().st_mode & 0o777 == 0o755
    entry = installed / "bin/chaldea-token-helper"
    entry.chmod(0o777)
    params["check_permissions"] = False
    assert not module.install(request)  # Existing user-client behavior is unchanged.
    params["check_permissions"] = True
    with pytest.raises(ValueError, match="unsafe ownership or write permissions"):
        module.install(request)
    entry.chmod(0o755)
    (installed / "src/cli.ts").write_text("modified")
    with pytest.raises(ValueError, match="differs from manifest"):
        module.install(request)
