"""Host credential selection; native configuration stays at the main golden bytes."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "roles/webmcp_interactive/tasks"


@pytest.mark.parametrize("enabled,installed,source,ok", [
    (False, "legacy", "legacy", True),
    (True, "legacy", "new", False),
    (True, "new", "legacy", False),
    (True, "missing", "new", False),
    (True, "other-arch", "new", False),
    (True, "new", "new", True),
])
def test_selector_aware_helper_preflight(tmp_path, enabled, installed, source, ok):
    tasks = yaml.safe_load((TASKS / "main.yml").read_text())
    gate = next(t for t in tasks if t["name"] ==
                "Require selector-aware helper before enabling host identity")
    hashes = {"new": "a" * 64, "legacy": "b" * 64, "other-arch": "c" * 64}
    target = {"exists": installed != "missing"}
    if installed != "missing":
        target["checksum"] = hashes[installed]
    play = tmp_path / "preflight.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "connection": "local", "gather_facts": False,
        "vars": {
            "chaldea_host_identity_enabled": enabled,
            "ansible_facts": {"architecture": "x86_64"},
            "webmcp_interactive_host_identity_helper_checksums": {
                "x86_64": hashes["new"], "aarch64": hashes["other-arch"]},
            "webmcp_interactive_helper_target": {"stat": target},
            "webmcp_interactive_helper_source_stat": {"stat": {"checksum": hashes[source]}},
        }, "tasks": [gate],
    }]))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                            capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    if not ok:
        assert "refusing legacy fallback" in result.stdout


def test_native_adapters_match_main_golden():
    # Git blob IDs at 72add22, except the two mcp_registrations files, which
    # were deliberately extended for the Antigravity provider (PR #194), for
    # Antigravity's managed web MCP bridge entries (PR #202), and for the
    # closed HoloNet library manager entry (PR #203).
    # Jobs omit .git, so check the golden bytes directly.
    for path, expected in {
        "roles/mcp_registrations/library/mcp_registration.py": "3b3b082e57e2b3df5f7f433aff686395f9060ffe",
        "roles/mcp_registrations/tasks/main.yml": "b9250daf02b4a36c91de98ea627d08f6d897b970",
        "roles/webmcp_interactive/templates/opencode-webmcp-jocasta.js.j2": "70f98a89a833cc61e43733ac4b8096096e4215b2",
    }.items():
        data = (ROOT / path).read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == expected


@pytest.mark.parametrize("host", ["laptop", "omarchy-pc", "agent-a", "agent-b"])
@pytest.mark.parametrize("enabled", [False, True])
def test_rendered_credentials_and_missing_file_refusal(tmp_path, host, enabled):
    assert Path.home().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    main = yaml.safe_load((TASKS / "main.yml").read_text())
    writer = yaml.safe_load((TASKS / "holonet-writer.yml").read_text())
    credentials = []
    for task in main + writer:
        for value in task.get("loop", []):
            if isinstance(value, str) and ".app-password" in value:
                credentials.append(value)
    assert len(credentials) == 5
    play_tasks = []
    for value, profile in zip(credentials, ["ov-interactive-codex", "ov-full-interactive",
                                           "shizune-interactive", "holonet-interactive",
                                           "holonet-recommendations"]):
        play_tasks += [
            {"name": "Render credential", "ansible.builtin.set_fact": {"rendered": value}},
            {"name": "Compare selected credential", "ansible.builtin.assert": {"that": [
                "rendered == expected"]}, "vars": {"expected":
                    str(tmp_path / ".config/chaldea/authentik") + "/" +
                    ("host" if enabled else profile) + ".app-password"}},
        ]
    custody = yaml.safe_load((TASKS / "host-identity.yml").read_text())[:2]
    # The actual role tasks must refuse missing host credentials when selected.
    play_tasks += custody
    play = tmp_path / "proof.yml"
    play.write_text(yaml.safe_dump([{"hosts": host, "connection": "local", "gather_facts": False,
        "vars": {"fleet_home": str(tmp_path), "chaldea_host_identity_enabled": enabled,
                 "ansible_facts": {"user_uid": os.getuid()}}, "tasks": play_tasks}]))
    result = subprocess.run(["ansible-playbook", "-i", host + ",", str(play)],
                            capture_output=True, text=True)
    if enabled:
        assert result.returncode != 0
        assert "host.app-password is missing or unsafe" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr


HOST_ARCHS = {
    "laptop": "aarch64",
    "omarchy-pc": "x86_64",
    "agent-a": "x86_64",
    "agent-b": "x86_64",
}


def test_host_identity_helper_pin_parity(tmp_path):
    """Every host-identity host's helper sha256 must match its capability pin per arch."""
    host_vars_root = ROOT / "inventory/host_vars"
    host_arches: dict[str, list[str]] = {}
    for host_dir in sorted(p for p in host_vars_root.iterdir() if p.is_dir()):
        host = host_dir.name
        enabled = False
        scoped_checksums: dict[str, str] = {}
        for path in sorted(host_dir.glob("*.yml")):
            data = yaml.safe_load(path.read_text())
            if not isinstance(data, dict):
                continue
            if data.get("chaldea_host_identity_enabled") is True:
                enabled = True
            if "webmcp_interactive_host_identity_helper_checksums" in data:
                checksums = data["webmcp_interactive_host_identity_helper_checksums"]
                assert isinstance(checksums, dict) and checksums, f"{path}: empty capability pin map"
                scoped_checksums.update(checksums)
        if not enabled and not scoped_checksums:
            continue
        arches = sorted(scoped_checksums)
        if host in HOST_ARCHS and HOST_ARCHS[host] not in arches:
            arches.append(HOST_ARCHS[host])
        assert arches, f"{host}: host-identity host has no known architecture to verify"
        host_arches[host] = arches

    assert set(host_arches) >= {"laptop", "omarchy-pc", "agent-a", "agent-b"}

    plays = []
    for host, arches in sorted(host_arches.items()):
        tasks = []
        for arch in arches:
            tasks.append({
                "name": f"Assert helper and capability pins match for {host} ({arch})",
                "ansible.builtin.assert": {
                    "that": [
                        "ansible_facts.architecture in webmcp_interactive_host_identity_helper_checksums",
                        "webmcp_interactive_helper_sha256 is string",
                        "webmcp_interactive_helper_sha256 is match('^[0-9a-f]{64}$')",
                        "webmcp_interactive_host_identity_helper_checksums[ansible_facts.architecture] == webmcp_interactive_helper_sha256",
                    ],
                    "fail_msg": (
                        f"{host} ({arch}): webmcp_interactive_helper_sha256 "
                        "does not match webmcp_interactive_host_identity_helper_checksums[arch]"
                    ),
                },
                "vars": {"ansible_facts": {"architecture": arch}},
            })
        plays.append({
            "hosts": host,
            "connection": "local",
            "gather_facts": False,
            "tasks": tasks,
        })

    play = tmp_path / "helper-pin-parity.yml"
    play.write_text(yaml.safe_dump(plays))
    result = subprocess.run(
        ["ansible-playbook", "-i", str(ROOT / "inventory/hosts.yml"), str(play)],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

