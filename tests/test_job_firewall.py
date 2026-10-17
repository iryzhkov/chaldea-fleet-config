"""Compute-port firewall and collection-free package provisioning regressions."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pytest
import yaml
from jinja2 import Environment
from ansible.plugins.filter.core import FilterModule
from ansible.plugins.filter.mathstuff import FilterModule as MathFilters
from ansible.plugins.test.core import TestModule as AnsibleTests

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "roles/chaldea_job_host"


def environment():
    env = Environment()
    env.filters.update(FilterModule().filters())
    env.filters.update(MathFilters().filters())
    env.tests.update(AnsibleTests().tests())
    return env


def tasks(name="main"):
    return yaml.safe_load((ROLE / f"tasks/{name}.yml").read_text())


def enabled(task, **values):
    conditions = task.get("when", [])
    if isinstance(conditions, str):
        conditions = [conditions]
    return all(environment().compile_expression(condition)(**values) for condition in conditions)


def render(name, **overrides):
    values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    values.update(overrides)
    return environment().from_string((ROLE / f"templates/{name}.j2").read_text()).render(**values)


@pytest.mark.parametrize("sources", [
    [{"ip": "192.0.2.1"}],
    [{"ip": "2001:db8::1"}],
    [{"ip": "192.0.2.1"}, {"ip": "2001:db8::1"}],
])
def test_rendered_firewall_is_only_the_compute_tcp_port_for_both_families(sources):
    text = render("chaldea-job.nft", chaldea_job_host_sources=sources)
    assert text.startswith("# One atomic transaction")
    assert "add table inet chaldea_job\ndelete table inet chaldea_job" in text
    assert "type ipv4_addr" in text and "type ipv6_addr" in text
    assert "type filter hook input priority filter; policy accept;" in text
    rules = [line.strip() for line in text.splitlines() if line.strip().startswith("tcp ")]
    assert rules == ["tcp dport 2222 ip saddr @sources4 accept",
                     "tcp dport 2222 ip6 saddr @sources6 accept", "tcp dport 2222 drop"]
    assert "flush" not in text and "forward" not in text and "output" not in text
    assert "include " not in text
    for source in sources:
        assert source["ip"] in text


def netns_tools():
    nft = shutil.which("nft")
    unshare = shutil.which("unshare")
    if not nft or not unshare:
        pytest.skip("nft/unshare absent: rendered nft -c validation needs an existing private-netns toolchain")
    probe = subprocess.run([unshare, "-Urn", nft, "list", "tables"], capture_output=True)
    if probe.returncode:
        pytest.skip("private user/network namespace or nft capability unavailable; host rules remain untouched")
    return nft, unshare


@pytest.mark.parametrize("sources", [[{"ip": "127.0.0.1"}], [{"ip": "::1"}],
                                     [{"ip": "127.0.0.1"}, {"ip": "::1"}]])
def test_nft_check_and_replacement_preserve_other_tables(sources):
    nft, unshare = netns_tools()
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "job.nft"
        config.write_text(render("chaldea-job.nft", chaldea_job_host_sources=sources))
        code = """
import json,subprocess,sys
nft,config=sys.argv[1:]
def run(*args,**kwargs):
    result=subprocess.run([nft,*args],text=True,capture_output=True,**kwargs)
    assert result.returncode==0,result.stderr
    return result
run('-f','-',input='table ip filter { chain DOCKER { counter return; }; }\\ntable inet operator { chain input { type filter hook input priority filter; policy accept; }; }\\n')
before={name:run('-j','list','table',family,name).stdout for family,name in [('ip','filter'),('inet','operator')]}
run('-c','-f',config)
assert subprocess.run([nft,'list','table','inet','chaldea_job'],capture_output=True).returncode != 0
for _ in range(2):
    run('-f',config)
    run('-c','-f',config)
    data=json.loads(run('-j','list','table','inet','chaldea_job').stdout)['nftables']
    assert len([x for x in data if 'rule' in x]) == 3
    for family,name in [('ip','filter'),('inet','operator')]:
        assert run('-j','list','table',family,name).stdout == before[name]
"""
        result = subprocess.run([unshare, "-Urn", sys.executable, "-I", "-c", code, nft, str(config)],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr


def test_nft_packets_allow_enrolled_source_drop_other_compute_and_preserve_other_ports():
    nft, unshare = netns_tools()
    ip = shutil.which("ip")
    if not ip:
        pytest.skip("ip absent: private-netns packet test needs loopback setup")
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "job.nft"
        config.write_text(render("chaldea-job.nft", chaldea_job_host_sources=[{"ip": "127.0.0.1"}]))
        code = """
import socket,subprocess,sys
nft,ip,config=sys.argv[1:]
subprocess.run([ip,'link','set','lo','up'],check=True)
subprocess.run([nft,'-c','-f',config],check=True)
subprocess.run([nft,'-f',config],check=True)
servers=[]
for port in (2222,22,7391,45011):
    server=socket.socket(); server.bind(('127.0.0.1',port)); server.listen(); servers.append(server)
    client=socket.socket(); client.bind(('127.0.0.1' if port==2222 else '127.0.0.2',0))
    client.settimeout(1); client.connect(server.getsockname())
    peer,_=server.accept(); peer.close(); client.close()
client=socket.socket(); client.bind(('127.0.0.2',0)); client.settimeout(.3)
try:
    client.connect(('127.0.0.1',2222))
    raise AssertionError('unenrolled source reached compute port')
except TimeoutError: pass
finally: client.close()
for server in servers: server.close()
"""
        result = subprocess.run([unshare, "-Urn", sys.executable, "-I", "-c", code,
                                 nft, ip, str(config)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr


def test_nft_unit_is_persistent_bounded_and_validates_before_loading():
    unit = render("chaldea-job-firewall.service")
    assert "Type=oneshot" in unit and "RemainAfterExit=yes" in unit
    assert "DefaultDependencies=no" in unit and "WantedBy=multi-user.target" in unit
    assert "Before=multi-user.target" not in unit and "Before=network" not in unit
    assert "TimeoutStartSec=5" in unit
    assert "ExecStartPre=/usr/bin/nft -c -f /etc/chaldea-job.nft" in unit
    assert "ExecStart=/usr/bin/nft -f /etc/chaldea-job.nft" in unit
    assert unit.index("ExecReload=/usr/bin/nft -c") < unit.index("ExecReload=/usr/bin/nft -f")
    assert "flush" not in unit and "/etc/nftables.conf" not in unit and "nftables.service" not in unit
    sshd = render("chaldea-job-sshd.service", chaldea_job_host_firewall="nft")
    assert "Requires=chaldea-job-firewall.service" in sshd
    assert "After=network.target chaldea-job-firewall.service" in sshd
    assert "ExecStartPre=/usr/bin/nft list table inet chaldea_job" in sshd
    assert "ufw" not in sshd
    nft = tasks("nft")
    assert nft[0]["ansible.builtin.template"]["validate"] == "/usr/bin/nft -c -f %s"
    assert nft[2]["ansible.builtin.systemd_service"]["name"] == "chaldea-job-firewall.service"


def test_ufw_tasks_and_handlers_are_skipped_in_nft_mode_and_selector_is_not_overwritten():
    main = tasks()
    guarded = [task for task in main if (
        "active firewall" in task["name"] or "ordinary UFW" in task["name"] or "persistent UFW" in task["name"])]
    assert len(guarded) == 3
    for task in guarded:
        assert not enabled(task, chaldea_job_host_firewall="nft")
        assert enabled(task, chaldea_job_host_firewall="ufw")
    assert all(task.get("register") != "chaldea_job_host_firewall" for task in main)
    handlers = yaml.safe_load((ROLE / "handlers/main.yml").read_text())
    ufw = next(task for task in handlers if task["name"] == "Reload job firewall")
    assert not enabled(ufw, chaldea_job_host_firewall="nft")
    assert handlers[0]["name"] == "Reload job nft firewall"  # before sshd restart
    check = next(task for task in main if "nft table before starting" in task["name"])
    assert check["ansible.builtin.command"]["argv"] == ["/usr/bin/nft", "list", "table", "inet", "chaldea_job"]
    start = next(t for t in main if t["name"] == "Start the restricted job SSH daemon")
    assert main.index(check) < main.index(start)
    assert not enabled(start, ansible_check_mode=True)
    restart = next(t for t in handlers if t["name"] == "Restart job sshd")
    assert not enabled(restart, ansible_check_mode=True)
    inventory = yaml.safe_load((ROOT / "inventory/hosts.yml").read_text())
    assert inventory["all"]["children"]["agent_hosts"]["hosts"]["agent-a"]["chaldea_job_host_firewall"] == "nft"


@pytest.mark.parametrize("family", ["Archlinux", "Debian"])
@pytest.mark.parametrize("firewall", ["ufw", "nft"])
def test_packages_use_core_pacman_or_apt_and_never_install_ufw_for_nft(family, firewall):
    package_tasks = tasks("packages")
    env = environment()
    expression = package_tasks[0]["ansible.builtin.set_fact"]["chaldea_job_host_required_packages"]
    packages = env.compile_expression(expression.removeprefix("{{ ").removesuffix(" }}"))(
        ansible_facts={"os_family": family}, chaldea_job_host_firewall=firewall)
    assert ("ufw" in packages) == (firewall == "ufw")
    assert ("openssh" in packages) == (family == "Archlinux")
    arch = next(t for t in package_tasks if "without a collection" in t["name"])
    values = {"ansible_facts": {"os_family": family}, "ansible_check_mode": False,
              "chaldea_job_host_missing_packages": ["bubblewrap", "passt"]}
    assert enabled(arch, **values) == (family == "Archlinux")
    assert not enabled(arch, **{**values, "ansible_check_mode": True})
    assert not enabled(arch, **{**values, "chaldea_job_host_missing_packages": []})
    command = env.compile_expression(arch["ansible.builtin.command"]["argv"][3:-3])(**values)
    assert command == ["pacman", "-S", "--needed", "--noconfirm", "bubblewrap", "passt"]
    for stdout, changed in [("(1/2) installing bubblewrap\n", True), ("there is nothing to do\n", False)]:
        assert env.compile_expression(arch["changed_when"])(chaldea_job_host_pacman={"stdout": stdout}) == changed
    apt = next(t for t in package_tasks if "with apt" in t["name"])
    assert enabled(apt, **values) == (family == "Debian")
    assert all("ansible.builtin.package" not in task for task in package_tasks)


def test_missing_packages_defer_version_assert_only_in_check_mode_with_an_explanation():
    main = tasks()
    baseline = next(t for t in main if "supported distro sandbox baseline" in t["name"])
    explain = next(t for t in main if "deferred version" in t["name"])
    for packages in ({}, {"bubblewrap": [{"version": "0.12.0"}]}):
        values = {"ansible_check_mode": True, "ansible_facts": {"packages": packages}}
        assert not enabled(baseline, **values)
        assert enabled(explain, **values)
        message = environment().from_string(explain["ansible.builtin.debug"]["msg"]).render(**values)
        assert "Skipping" in message and "passt" in message
        assert enabled(baseline, **{**values, "ansible_check_mode": False})
    installed = {"bubblewrap": [{"version": "0.12.0"}], "passt": [{"version": "2026_07_28.f8df3f1-1"}]}
    assert enabled(baseline, ansible_check_mode=True, ansible_facts={"packages": installed})


def image_module():
    path = ROLE / "files/chaldea-job-image"
    loader = importlib.machinery.SourceFileLoader("job_image_nocow", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("filesystem", ["btrfs", "ext4"])
def test_new_btrfs_image_sets_nocow_while_empty_before_formatting(filesystem):
    module = image_module()
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "job.ext4"
        calls = []
        def run(command, **_kwargs):
            calls.append(command)
            temporary = Path(command[-1])
            if command[0] == "chattr":
                assert temporary.stat().st_size == 0
                assert command[1] == "+C"
            else:
                assert command[0] == "mkfs.ext4"
                assert temporary.stat().st_size == 512 * 1024**2
                assert (len(calls) == 2) == (filesystem == "btrfs")
        with patch.object(module.subprocess, "check_output", return_value=filesystem + "\n"), \
             patch.object(module.subprocess, "run", side_effect=run):
            assert module.create(target, 512 * 1024**2, (os.getuid(), os.getgid()))
        assert any(call[0] == "chattr" for call in calls) == (filesystem == "btrfs")
        assert target.stat().st_size == 512 * 1024**2
        with patch.object(module.subprocess, "check_output") as probe:
            assert not module.create(target, 512 * 1024**2, (os.getuid(), os.getgid()))
            probe.assert_not_called()
