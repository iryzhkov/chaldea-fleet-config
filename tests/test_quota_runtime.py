"""Independent quota runtime preserves helper pins and ordinary observer renders."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import types

from ansible.plugins.filter.core import FilterModule
from jinja2 import Environment, StrictUndefined
import pytest
import yaml

from client_artifact_fixture import stage

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_client"


def safe(path):
    scratch = Path(os.environ["TMPDIR"]).resolve()
    assert not scratch.is_relative_to("/tmp")
    assert Path.home().is_relative_to(scratch)
    assert Path.home() != Path("/home/igor")
    assert path.resolve().is_relative_to(scratch)


def render(name, overrides=None):
    values = yaml.safe_load((ROLE / "defaults/main.yml").read_text()) | {
        "fleet_home": "/home/fixture",
        "chaldea_node_version": "26.10.0",
        "chaldea_client_t3_home": "/home/fixture/.t3",
        "chaldea_client_quota_token": "/home/fixture/.config/chaldea/t3-token",
        "chaldea_client_codex_home": "/home/fixture/.codex",
        "chaldea_client_codex_command": "/home/fixture/bin/codex",
    } | (overrides or {})
    env = Environment(trim_blocks=True, keep_trailing_newline=True, undefined=StrictUndefined)
    env.filters.update(FilterModule().filters())
    return env.from_string((ROLE / "templates" / name).read_text()).render(values)


def test_scoped_publisher_cannot_change_normal_observer_or_reader():
    normal = render("chaldea-quota.service.j2")
    quota = render("quota.json.j2")
    scope = dict(chaldea_client_quota_runtime_enabled=True,
                 chaldea_client_quota_runtime_version="client-v0.4.2",
                 chaldea_client_quota_runtime_sha256="a" * 64,
                 chaldea_client_quota_fleet={"enabled": True},
                 chaldea_client_claude_contexts=[{"providerInstanceId": "claudeAgent"}])
    sharing = render("chaldea-quota.service.j2", scope)
    assert "/opt/chaldea-token-helper/releases/client-v0.4.2/bin/chaldea" in sharing
    assert "--t3-base-dir %h/.t3 --token-file %h/.config/chaldea/t3-token" in sharing
    assert "--quota-config %h/.config/chaldea/quota-sharing.json" in sharing
    assert "--state-file %h/.local/state/chaldea/quota-sharing/observer.json" in sharing
    assert "--feed-command /usr/bin/true" in sharing
    assert "--restart-config %h/.config/chaldea/quota-sharing-runtime/chaldea/restart.json" in sharing
    assert "Environment=XDG_CONFIG_HOME=%h/.config/chaldea/quota-sharing-runtime\n" in sharing
    assert "Environment=XDG_STATE_HOME=%h/.local/state/chaldea/quota-sharing-runtime\n" in sharing
    assert "UnsetEnvironment=AKASHA_URL AKASHA_TOKEN_HELPER\n" in sharing
    assert "/current/" not in sharing and "--enable-provider-switch" not in sharing
    publisher = json.loads(render("quota.json.j2", scope))
    assert publisher["contexts"] == [] and "claudeContexts" not in publisher
    assert publisher["fleet"] == {"enabled": True}
    reader = json.loads(render("quota.json.j2", {"chaldea_client_quota_fleet": {"enabled": True}}))
    assert reader["contexts"] == json.loads(quota)["contexts"]
    assert reader["fleet"]["enabled"] is True
    assert render("chaldea-quota.service.j2") == normal
    assert render("quota.json.j2") == quota
    assert "quota-sharing" not in normal and "fleet" not in json.loads(quota)
    assert "--quota-config %h/.config/chaldea/quota.json\n" in normal


def test_independent_runtime_vars_preserve_all_helper_rendered_outputs():
    helper = ROOT / "roles/chaldea_token_helper/templates"
    env = Environment(trim_blocks=True, keep_trailing_newline=True, undefined=StrictUndefined)
    env.filters.update(FilterModule().filters())
    values = dict(
        chaldea_token_helper_issuer=dict(uid=995, key_file="/private/issuer.pem",
                                         name="chaldea:laptop", kid="laptop-key"),
        chaldea_token_helper_state="/private/helper-state",
        chaldea_access_paths=dict(bundle="/public/bundle", root="/etc/trust", clock_health="/public/clock"),
        chaldea_token_helper_grants=[dict(uid=1001, audience="akasha", action="append",
            source="timer", host="laptop", kind="timer_run", profile="timer-service", project="chaldea")],
        chaldea_token_helper_node="/opt/chaldea-token-helper/node/bin/node",
        chaldea_token_helper_release="/opt/chaldea-token-helper/releases/client-v0.4.0",
    )
    quota = dict(chaldea_client_quota_runtime_enabled=True,
                 chaldea_client_quota_runtime_version="client-v0.4.2",
                 chaldea_client_quota_runtime_sha256="a" * 64,
                 chaldea_client_quota_fleet={"enabled": True})
    for name in ("issuer-command.j2", "token-helper.json.j2", "sudoers.j2"):
        template = env.from_string((helper / name).read_text())
        before = template.render(values)
        assert template.render(values | quota) == before
        assert "client-v0.4.2" not in before
    assert "/releases/client-v0.4.0/bin/chaldea" in env.from_string(
        (helper / "issuer-command.j2").read_text()).render(values)


def run_subset(tmp_path, overrides):
    safe(tmp_path)
    play = tmp_path / "quota-runtime.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": overrides,
        "tasks": [{"ansible.builtin.include_role": {
            "name": "chaldea_client", "tasks_from": "quota-runtime"}}],
    }]))
    return subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                          cwd=ROOT, capture_output=True, text=True,
                          env=dict(os.environ, ANSIBLE_ROLES_PATH=str(ROOT / "roles")))


def test_defaultoff_subset_runs_without_any_protected_install(tmp_path):
    result = run_subset(tmp_path, {})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed=0" in result.stdout
    assert "chaldea_client_version" not in result.stdout


@pytest.mark.parametrize("version,digest", [
    ("client-v0.4.0", "a" * 64), ("client-v0.4.1", "a" * 64),
    ("client-v0.4.2\n", "a" * 64), ("client-v0.4.2", "not-a-digest"),
])
def test_invalid_release_refused_before_protected_path_access(tmp_path, version, digest):
    result = run_subset(tmp_path, dict(chaldea_client_quota_runtime_enabled=True,
                                      chaldea_client_quota_runtime_version=version,
                                      chaldea_client_quota_runtime_sha256=digest))
    assert result.returncode != 0
    assert "Inspect the already provisioned" not in result.stdout


def tree_receipt(root):
    return {str(p.relative_to(root)): (
        os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()
        if p.is_file() else "directory", p.lstat().st_mode & 0o777, p.lstat().st_uid)
        for p in root.rglob("*")}


def test_canonical_installer_side_by_side_check_apply_and_drift(tmp_path):
    safe(tmp_path)
    spec = importlib.util.spec_from_file_location("quota_release", ROOT / "library/chaldea_client_release.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = stage(tmp_path / "archive")
    protected = tmp_path / "protected"
    releases = protected / "releases"
    helper = releases / "client-v0.4.0"
    helper.mkdir(parents=True, mode=0o700)
    (helper / "helper-provenance").write_text("accepted private helper 0.4.0")
    (protected / "current").symlink_to("releases/client-v0.4.0")
    (protected / "issuer-launcher").write_text("immutable helper 0.4.0 launcher")
    (protected / "pin.json").write_text('{"version":"client-v0.4.0"}')
    before = tree_receipt(protected)
    request = types.SimpleNamespace(check_mode=True, params=dict(
        root=str(releases), version=fixture["chaldea_client_version"],
        archive=fixture["chaldea_client_archive_source"],
        manifest=fixture["chaldea_client_manifest_source"],
        sha256=fixture["chaldea_client_sha256"], check_permissions=True))
    assert module.install(request)
    assert tree_receipt(protected) == before
    request.check_mode = False
    assert module.install(request)
    installed = releases / fixture["chaldea_client_version"]
    installed.chmod(0o755)  # Only the new directory; the role performs this exact step.
    assert not module.install(request)
    after = tree_receipt(protected)
    assert all(after[path] == receipt for path, receipt in before.items())
    assert (installed / "bin/chaldea").stat().st_mode & 0o777 == 0o755
    assert (installed / "src/cli.ts").stat().st_mode & 0o777 == 0o644
    (installed / "src/cli.ts").write_text("drift")
    with pytest.raises(ValueError, match="differs from manifest"):
        module.install(request)
    assert all(tree_receipt(protected)[path] == receipt for path, receipt in before.items())
