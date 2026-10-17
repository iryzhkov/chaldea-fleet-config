"""Role contracts retained with fleet configuration after host code moves."""
from pathlib import Path
import json
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_job_host"
DEFAULTS = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())["chaldea_job_host_toolchain_versions"]


def test_public_host_e2e_ssh_fixtures_match_deployed_templates():
    import os
    import re
    import urllib.request
    import pytest
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())
    ref = os.environ.get("CHALDEA_HOST_TEST_SOURCE_REF")
    if not ref and inventory["chaldea_host_sha256"] == "0" * 64:
        pytest.skip("host release bootstrap is pending; supply an exact candidate source ref")
    ref = ref or inventory["chaldea_host_version"]
    assert re.fullmatch(r"[a-f0-9]{40}|host-v[0-9]+[.][0-9]+[.][0-9]+(?:[.-][A-Za-z0-9.-]+)?", ref)
    for name in ("authorized_keys.j2", "chaldea-job-sshd.conf.j2"):
        url = f"https://raw.githubusercontent.com/iryzhkov/chaldea/{ref}/host/tests/fixtures/{name}"
        with urllib.request.urlopen(url, timeout=30) as response:
            frozen = response.read()
        assert frozen == (ROLE / "templates" / name).read_bytes(), (
            f"Chaldea {ref} E2E fixture {name} differs from the deployed fleet template"
        )

def test_inventory_official_toolchain_pin_schema():
    import re
    inventory = yaml.safe_load((ROOT / "inventory/group_vars/all.yml").read_text())
    versions = inventory["chaldea_job_host_toolchain_versions"]
    checksums = inventory["chaldea_job_host_toolchain_checksums"]
    targets = {"x86_64": "x86_64-unknown-linux-gnu", "aarch64": "aarch64-unknown-linux-gnu"}
    for tool, configured in versions.items():
        assert tool in ("node", "go", "rust", "uv") and configured
        for version in configured:
            assert re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", version)
            assert set(checksums[tool][version]) == set(targets)
            for arch, target in targets.items():
                expected = {
                    "node": {f"node-v{version}-linux-{'x64' if arch == 'x86_64' else 'arm64'}.tar.xz"},
                    "go": {f"go{version}.linux-{'amd64' if arch == 'x86_64' else 'arm64'}.tar.gz"},
                    "uv": {f"uv-{target}.tar.gz"},
                    "rust": {f"{part}-{version}-{target}.tar.xz" for part in ("rustc", "cargo", "rust-std")},
                }[tool]
                pins = checksums[tool][version][arch]
                assert set(pins) == expected
                assert all(re.fullmatch(r"[a-f0-9]{64}", digest) for digest in pins.values())


def test_rendered_role_boot_limits_mixed_case_deny_and_rollback():
    import yaml
    from jinja2 import Environment, Template
    from ansible.plugins.test.core import TestModule
    role = ROLE
    tasks = yaml.safe_load((role / "tasks/main.yml").read_text())
    guarded = next(t for t in tasks if "block" in t and "rollback" in t["name"])
    check = next(t for t in guarded["block"] if "failed_when" in t)
    env = Environment()
    env.tests.update(TestModule().tests())
    for output in ("DenyUsers chaldea-job\n", "denyusers chaldea-job\n", "DENYUSERS other chaldea-job\n"):
        value = env.from_string("{{ " + check["failed_when"] + " }}").render(
            chaldea_job_host_effective_sshd={"stdout": output})
        assert value == "False"
    assert guarded["rescue"][0]["ansible.builtin.file"]["state"] == "absent"
    defaults = yaml.safe_load((role / "defaults/main.yml").read_text())
    defaults.update(chaldea_job_host_memory_max="4G", chaldea_job_host_cpu_quota="400%",
                    chaldea_job_host_state_root="/home/chaldea-job/jobs",
                    chaldea_job_host_image="/home/chaldea-job-state.ext4",
                    chaldea_job_host_sshd_binary="/usr/bin/sshd")
    mount = Template((role / "templates/chaldea-job.mount.j2").read_text()).render(**defaults)
    unit = Template((role / "templates/chaldea-job-sshd.service.j2").read_text()).render(**defaults)
    assert "DefaultDependencies=no" in mount and "nofail" in mount and "TimeoutSec=5" in mount
    assert "ConditionPathExists=" in mount and "WantedBy=multi-user.target" in mount
    assert "Requires=" not in mount and "Before=multi-user.target" not in mount
    assert ".mount" not in unit and "Requires=" not in unit
    assert "MemoryMax=4G" in unit and "TasksMax=256" in unit
    assert "CPUWeight=10" in unit and "IOWeight=10" in unit
    assert "state: started" in (role / "tasks/main.yml").read_text()


def test_role_memory_and_top_level_slice_budget_and_apply_smoke():
    import yaml
    from jinja2 import Environment, Template
    from ansible.plugins.filter.core import FilterModule
    from ansible.plugins.filter.mathstuff import FilterModule as MathFilters
    from ansible.plugins.test.core import TestModule
    role = ROLE
    defaults = yaml.safe_load((role / "defaults/main.yml").read_text())
    inventory = yaml.safe_load((role.parents[1] / "inventory/hosts.yml").read_text())
    hosts = inventory["all"]["children"]["agent_hosts"]["hosts"]
    assert hosts["agent-b"]["chaldea_job_host_memory_max"] == "4G"
    env = Environment()
    env.filters.update(FilterModule().filters())
    env.filters.update(MathFilters().filters())
    env.tests.update(TestModule().tests())
    for name, ram in {"agent-a": 20, "agent-b": 8, "laptop": 24, "omarchy-pc": 32}.items():
        assert env.filters["human_to_bytes"](hosts[name]["chaldea_job_host_memory_max"]) <= ram * 1024**3 // 2
    for ram_mb in (2048, 8192, 32768):
        value = int(env.from_string(defaults["chaldea_job_host_memory_max"]).render(
            ansible_facts={"memtotal_mb": ram_mb}))
        assert value <= ram_mb * 1024**2 // 2
    quota = env.from_string(defaults["chaldea_job_host_cpu_quota"]).render(
        ansible_facts={"processor_vcpus": 8})
    assert quota == "400%"
    unit = Template((role / "templates/chaldea-job-sshd.service.j2").read_text()).render(**defaults)
    budget = Template((role / "templates/chaldea.slice.j2").read_text()).render(
        **{**defaults, "chaldea_job_host_cpu_quota": quota})
    assert "Slice=chaldea.slice" in unit  # no dash: direct sibling of user.slice
    assert "CPUWeight=10" in budget and "CPUQuota=400%" in budget
    assert "Requires=" not in budget
    tasks = yaml.safe_load((role / "tasks/main.yml").read_text())
    smoke = next(t for t in tasks if "Smoke test" in t["name"])
    assert smoke["become"] is True
    assert "--reuid={{ chaldea_job_host_user }}" in smoke["ansible.builtin.command"]["argv"]
    hardware = next(t for t in tasks if "CPU and RAM facts" in t["name"])
    assert "hardware" in hardware["ansible.builtin.setup"]["gather_subset"]
    assert "--smoke-test" in smoke["ansible.builtin.command"]["argv"]
    assert "chaldea_job_host_mount_ready.rc == 0" in smoke["when"]
    baseline = next(t for t in tasks if "supported distro sandbox baseline" in t["name"])
    for version in ("2026_07_28.f8df3f1-1", "0.0~git20250503.587980c-2+deb13u1"):
        assert env.from_string("{{ " + baseline["ansible.builtin.assert"]["that"][1] + " }}").render(
            ansible_facts={"packages": {"passt": [{"version": version}]}}) == "True"
    assert env.from_string("{{ " + baseline["ansible.builtin.assert"]["that"][1] + " }}").render(
        ansible_facts={"packages": {"passt": [{"version": "2024_12_01.old"}]}}) == "False"


def test_slot_inventory_and_shared_limits_rendered():
    import yaml
    from jinja2 import Template
    role = ROLE
    defaults = yaml.safe_load((role / "defaults/main.yml").read_text())
    hosts = yaml.safe_load((role.parents[1] / "inventory/hosts.yml").read_text())["all"]["children"]["agent_hosts"]["hosts"]
    assert defaults["chaldea_job_host_slots"] == 1
    for host, slots in {"agent-a": 3, "omarchy-pc": 2, "agent-b": 1, "laptop": 1}.items():
        values = {**defaults, **hosts[host], "chaldea_job_host_cpu_quota": "400%"}
        assert values["chaldea_job_host_slots"] == slots
        sshd = Template((role / "templates/chaldea-job-sshd.conf.j2").read_text()).render(**values)
        assert f"MaxSessions {slots + 1}\n" in sshd
        assert "MaxStartups" not in sshd  # retain the dedicated daemon's default
        budget = Template((role / "templates/chaldea.slice.j2").read_text()).render(**values)
        assert "MemoryMax=" + hosts[host]["chaldea_job_host_memory_max"] in budget
        assert "TasksMax=" + str(hosts[host]["chaldea_job_host_tasks_max"]) in budget
        assert "MemorySwapMax=0" in budget
        assert "CPUQuota=400%" in budget

def test_role_fails_clearly_when_inventory_versions_are_unset(tmp_path):
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    assert "chaldea_job_host_toolchain_versions" not in defaults
    tasks = yaml.safe_load((ROLE / "tasks/toolchains.yml").read_text())
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{
        "name": "Check required inventory versions", "hosts": "localhost",
        "gather_facts": False, "tasks": [tasks[0]],
    }]))
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "Set chaldea_job_host_toolchain_versions in inventory" in result.stdout
    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play),
                             "-e", json.dumps({"chaldea_job_host_toolchain_versions": DEFAULTS})],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_role_passes_pins_and_never_touches_job_owned_lock_path():
    tasks = yaml.safe_load((ROLE / "tasks/toolchains.yml").read_text())
    install = next(t for t in tasks if "ansible.builtin.command" in t)
    assert install["become"] is True
    assert "chaldea_job_host_mount_ready.rc == 0" in install["when"]
    assert "--admission-lock" in install["ansible.builtin.command"]["argv"]
    assert "--checksums" in install["ansible.builtin.command"]["argv"]
    assert not any("ansible.builtin.file" in t and "admission.lock" in
                   t["ansible.builtin.file"]["path"] for t in tasks)
    main = (ROLE / "tasks/main.yml").read_text()
    assert main.index("Secure the mounted filesystem") < main.index("Provision pinned job toolchains")
    assert main.index("Provision pinned job toolchains") < main.index("Install the job host configuration")


