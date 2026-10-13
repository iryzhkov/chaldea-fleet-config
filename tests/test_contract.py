"""Offline contract checks. External observation custody is verified at handoff."""
import copy
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node):
    result = {}
    for key, value in node.value:
        key = loader.construct_object(key)
        if key in result:
            raise ValueError("duplicate YAML key")
        result[key] = loader.construct_object(value)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def read(path):
    return yaml.load((ROOT / path).read_text(), Loader=UniqueLoader)


def pins_valid(p):
    p = p["steward"]
    assert p["repository"] == "iryzhkov/t3-steward"
    assert re.fullmatch(r"0\.\d+\.\d+-rc\.\d+", p["version"])
    assert p["tag"] == "v" + p["version"]
    assert re.fullmatch("[0-9a-f]{40}", p["source"])
    assert p["machine_arch"] == {"x86_64": "amd64", "aarch64": "arm64"}
    assets = p["assets"]
    assert len(assets) == 2
    assert {a["arch"] for a in assets} == set(p["machine_arch"].values())
    for a in assets:
        assert a["os"] == "linux"
        assert a["name"] == f't3-steward_{p["version"]}_linux_{a["arch"]}.tar.gz'
        assert re.fullmatch("[0-9a-f]{64}", a["sha256"])


def reference_valid(ref):
    assert isinstance(ref, dict) and set(ref) == {"kind", "path"}
    assert ref["kind"] in {"encrypted", "local_file"}
    assert isinstance(ref["path"], str) and ref["path"]
    assert not any(ord(c) < 32 for c in ref["path"])
    path = PurePosixPath(ref["path"])
    assert ".." not in path.parts and "\\" not in ref["path"]
    if ref["kind"] == "encrypted":
        assert not path.is_absolute() and path.parts[0] == "secrets"
        assert ref["path"].endswith(".sops.yaml")
    else:
        assert path.is_absolute() and len(path.parts) > 1


def workflow_valid(workflow):
    assert set(workflow) == {"name", "on", "permissions", "jobs"}
    assert workflow["name"] == "ci"
    assert set(workflow["on"]) == {"pull_request", "push"}
    assert workflow["on"]["pull_request"] is None
    assert workflow["on"]["push"] == {"branches": ["main"]}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"ci"}
    job = workflow["jobs"]["ci"]
    assert set(job) == {"runs-on", "steps"}
    steps = job["steps"]
    assert [s["run"] for s in steps if "run" in s] == [
        "bash tools/with-ci-env.sh python3 -m unittest discover -s tests -v",
        "bash tools/with-ci-env.sh ansible-lint"]
    for step in steps:
        assert set(step) <= {"uses", "with", "run"}
        if "uses" in step:
            assert re.fullmatch(r"actions/(checkout|setup-python)@[0-9a-f]{40}", step["uses"])
    assert "secrets." not in json.dumps(workflow)


def observed_path_valid(value):
    assert isinstance(value, str) and value.startswith("/") and not value.startswith("//")
    assert len(PurePosixPath(value).parts) > 1
    assert not any(ord(c) < 32 or ord(c) == 127 for c in value)
    assert "\\" not in value
    assert not any(part in {"", ".", ".."} for part in value.split("/")[1:])


def inventory_valid(inv):
    all_ = inv["all"]
    hosts = all_["children"]["fleet_targets"]["hosts"]
    vars_ = all_["vars"]
    top = vars_["topology_authority"]
    runner = all_["children"]["pull_runner"]["hosts"]
    assert list(runner) == [top["sole_pull_runner"]]
    order = top["worker_order"] + [top["coordinator_last"]]
    assert list(hosts) == order and len(set(order)) == 6
    assert re.fullmatch("[0-9a-f]{64}", vars_["observation_sha256"])
    assert vars_["probe_limitations"] and vars_["runner_resolution_provenance"]
    for index, (name, h) in enumerate(hosts.items(), 1):
        assert h["desired_order"] == index
        coordinator = name == top["coordinator_last"]
        assert h["desired_role"] == ("coordinator" if coordinator else "worker")
        assert h["desired_execution"] is (not coordinator)
        assert h["adopted"] is False
        assert h["ansible_connection"] == ("local" if name in runner else "ssh")
        assert h["ansible_user"] == h["runner_ssh"]["user"] == h["observed_user"]
        assert h["ansible_host"] == h["runner_ssh"]["hostname"]
        assert h["ansible_port"] == int(h["runner_ssh"]["port"])
        if "proxyjump" in h["runner_ssh"]:
            assert h["ansible_ssh_common_args"] == "-o ProxyJump=" + h["runner_ssh"]["proxyjump"]
        assert h["observed_catalog"]["connection"] == "persistent-ssh"
        assert h["observed_catalog"]["accept_backlog"] is True
        assert h["observed_catalog"]["address"]
        assert h["probe"]["provenance"]["observed_at_utc"]
        assert h["observed_os_release"]["ID"] and h["observed_kernel"] == "Linux"
        assert h["observed_machine"] in {"x86_64", "aarch64"}
        assert h["observed_config_exists"] is True
        assert h["observed_config_path"].startswith(h["observed_home"] + "/")
        assert isinstance(h["observed_hostname"], str)
        assert re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", h["observed_hostname"])
        candidates = h["observed_state_path_candidates"]
        assert isinstance(candidates, list) and candidates
        for path in candidates:
            observed_path_valid(path)
        for service in ("t3-steward.service", "t3-steward-worker.service"):
            s = h["observed_services"][service]
            assert [s[k] for k in ("LoadState", "ActiveState", "SubState")] == ["loaded", "active", "running"]
            assert s["FragmentPath"].startswith(h["observed_home"] + "/")
            runtime = h["observed_runtime_service_paths"][service]
            assert runtime["executable"] == h["observed_home"] + "/.local/bin/t3-steward"
            args = runtime["explicit_config_arguments"]
            expected = h["observed_config_path"] if service == "t3-steward.service" else h["observed_home"] + "/.config/t3-steward/persistent-worker.yaml"
            assert args == [expected]
            descriptors = h["observed_open_state_database_fds"][service]
            assert isinstance(descriptors, list)
            for path in descriptors:
                observed_path_valid(path)
        assert h.get("observed_configured_paths", {}).get(".state_path", "") == ""


class Contract(unittest.TestCase):
    def setUp(self):
        self.inventory = read("inventory/hosts.yml")
        self.hosts = self.inventory["all"]["children"]["fleet_targets"]["hosts"]

    def test_pins_and_mutations(self):
        pins = read("pins.yml")
        pins_valid(pins)
        changes = [
            ("repository", "other/project"), ("tag", "latest"), ("source", "main"),
            ("version", "latest"), ("source", "a" * 39),
            ("machine_arch", {"x86_64": "arm64", "aarch64": "arm64"}),
            ("assets", pins["steward"]["assets"][:1]),
            ("assets", [pins["steward"]["assets"][0]] * 2),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(pins)
                bad["steward"][key] = value
                with self.assertRaises(AssertionError):
                    pins_valid(bad)
        for key, value in [("sha256", "bad"), ("name", "wrong.tar.gz"),
                           ("os", "darwin"), ("arch", "unknown")]:
            bad = copy.deepcopy(pins)
            bad["steward"]["assets"][0][key] = value
            with self.assertRaises(AssertionError):
                pins_valid(bad)
        with self.assertRaises(ValueError):
            yaml.load("a: 1\na: 2\n", Loader=UniqueLoader)

    def test_inventory_and_mutations(self):
        inventory_valid(self.inventory)
        for key, value in [("adopted", True), ("observed_catalog", {"connection": "ssh", "accept_backlog": False}),
                           ("observed_config_path", ""), ("ansible_connection", "persistent-ssh"),
                           ("desired_execution", False), ("desired_order", 99),
                           ("observed_runtime_service_paths", {})]:
            bad = copy.deepcopy(self.inventory)
            bad["all"]["children"]["fleet_targets"]["hosts"][next(iter(self.hosts))][key] = value
            with self.subTest(key=key), self.assertRaises((AssertionError, KeyError)):
                inventory_valid(bad)
        bad = copy.deepcopy(self.inventory)
        bad["all"]["children"]["pull_runner"]["hosts"]["synthetic_second_runner"] = {}
        with self.assertRaises(AssertionError):
            inventory_valid(bad)
        bad = copy.deepcopy(self.inventory)
        bad["all"]["vars"]["topology_authority"]["worker_order"].reverse()
        with self.assertRaises(AssertionError):
            inventory_valid(bad)
        top = self.inventory["all"]["vars"]["topology_authority"]
        coordinator = self.hosts[top["coordinator_last"]]
        self.assertTrue(coordinator["observed_catalog"]["accept_backlog"])
        self.assertFalse(coordinator["desired_execution"])
        self.assertEqual(coordinator["observed_open_state_database_fds"]["t3-steward-worker.service"], [])
        self.assertTrue(any(h.get("observed_config_path_probe_error") for h in self.hosts.values()))
        self.assertTrue(any("self-SSH refused" in h["probe"]["provenance"]["method"] for h in self.hosts.values()))
        self.assertTrue(any(h["observed_state_path_candidates"][0] !=
                            h["observed_open_state_database_fds"]["t3-steward.service"][0]
                            for h in self.hosts.values()))

    def test_references_and_defaults(self):
        defaults = read("inventory/group_vars/all.yml")
        self.assertIs(defaults["pull_timer_enabled"], False)
        self.assertIs(defaults["live_preflight_enabled"], False)
        self.assertEqual(defaults["config_revision"], "fetched-git-head")
        self.assertEqual(defaults["reference_schema"], {"kinds": ["encrypted", "local_file"], "fields": ["kind", "path"]})
        for ref in defaults["credential_references"]:
            reference_valid(ref)
        for ref in [{"kind": "encrypted", "path": "secrets/synthetic.sops.yaml"},
                    {"kind": "local_file", "path": "/protected/synthetic"}]:
            reference_valid(ref)
        for ref in [{}, {"kind": "encrypted", "path": "../payload"},
                    {"kind": "local_file", "path": "relative"},
                    {"kind": "encrypted", "path": "secrets/../x.sops.yaml"},
                    {"kind": "encrypted", "path": "secrets/x.sops.yaml", "token": "inline"},
                    {"kind": "inline", "path": "payload"}, {"kind": "local_file", "path": 1}]:
            with self.subTest(ref=ref), self.assertRaises(AssertionError):
                reference_valid(ref)
        rule, = read(".sops.yaml")["creation_rules"]
        self.assertRegex(rule["age"], r"^age1[0-9a-z]{58}$")
        self.assertTrue(re.search(rule["path_regex"], "secrets/synthetic.sops.yaml"))
        self.assertFalse(re.search(rule["path_regex"], "public.yaml"))

    def test_workflow_and_scaffolds(self):
        workflow = read(".github/workflows/ci.yml")
        workflow_valid(workflow)
        for key, value in [("name", "deploy"), ("on", {"push": {"branches": ["main"]}}),
                           ("on", {"pull_request": {"paths": ["restricted"]}, "push": {"branches": ["main"]}}),
                           ("permissions", {"contents": "write"}), ("env", {"TOKEN": "${{ secrets.TOKEN }}"})]:
            bad = copy.deepcopy(workflow)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                workflow_valid(bad)
        bad = copy.deepcopy(workflow)
        bad["jobs"]["ci"]["steps"][0]["uses"] = "actions/checkout@main"
        with self.assertRaises(AssertionError):
            workflow_valid(bad)
        bad = copy.deepcopy(workflow)
        bad["jobs"]["ci"]["steps"][-1]["run"] = "ansible-lint"
        with self.assertRaises(AssertionError):
            workflow_valid(bad)
        self.assertEqual(workflow["name"], "ci")
        self.assertEqual(set(workflow["on"]), {"pull_request", "push"})
        self.assertEqual(workflow["on"]["push"], {"branches": ["main"]})
        self.assertIsNone(workflow["on"]["pull_request"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"ci"})
        steps = workflow["jobs"]["ci"]["steps"]
        commands = ["bash tools/with-ci-env.sh python3 -m unittest discover -s tests -v",
                    "bash tools/with-ci-env.sh ansible-lint"]
        self.assertEqual([s["run"] for s in steps if "run" in s], commands)
        for s in steps:
            if "uses" in s:
                self.assertRegex(s["uses"], r"^actions/(checkout|setup-python)@[0-9a-f]{40}$")
        self.assertEqual(steps[1]["with"]["python-version"], "3.13.5")
        plays = read("fleet.yml")
        self.assertEqual(plays[0]["hosts"], "localhost")
        self.assertEqual(plays[0]["connection"], "local")
        self.assertFalse(plays[0]["gather_facts"])
        self.assertEqual(plays[1]["hosts"], "pull_runner")
        for play, role in zip(plays[2:], ("worker", "coordinator")):
            self.assertEqual(play["hosts"], "adopted_" + role)
            self.assertEqual(play["roles"], [role])
            self.assertEqual(play["order"], "inventory")
            self.assertEqual(play["serial"], 1)
            self.assertTrue(play["any_errors_fatal"])
            self.assertFalse(play["gather_facts"])
        lint = read(".ansible-lint")
        self.assertTrue(lint["offline"])
        self.assertIn({"tasks": "roles/*/tasks/*.yml"}, lint["kinds"])

    def test_host_literal_custody(self):
        paths = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        literals = set(self.hosts)
        for h in self.hosts.values():
            literals.update([h["ansible_host"], h["observed_hostname"], h["probe"]["ssh_alias"]])
            literals.add(h["observed_home"])
            literals.add(h["observed_user"])
        for path in paths:
            if path == "inventory/hosts.yml":
                continue
            text = (ROOT / path).read_text()
            # Required repository namespaces are not host-user declarations.
            text = re.sub(r"[A-Za-z0-9_-]+/(t3-steward|chaldea-fleet-config)", "repository", text)
            for literal in literals:
                self.assertFalse(re.search(r"(?<![\w-])" + re.escape(literal) + r"(?![\w-])", text),
                                 (path, literal))

    def test_syntax(self):
        executable = shutil.which("ansible-playbook")
        self.assertEqual(Path(executable).parent, ROOT / ".venv-ci/bin")
        result = subprocess.run([executable, "-i", "inventory/hosts.yml", "--syntax-check", "fleet.yml"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_refusal(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache-ci") as temp:
            temp = Path(temp)
            sentinel = temp / "ssh-called"
            ssh = temp / "ssh"
            ssh.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 97\n")
            ssh.chmod(0o700)
            env = dict(os.environ, ANSIBLE_SSH_EXECUTABLE=str(ssh))
            inv = {"all": {"children": {
                "pull_runner": {"hosts": {"synthetic_runner": {"ansible_connection": "local"}}},
                "fleet_targets": {"hosts": {
                    "synthetic_runner": {"adopted": False, "desired_role": "worker", "desired_order": 1, "ansible_connection": "local"},
                    "synthetic_remote": {"adopted": False, "desired_role": "coordinator", "desired_order": 2, "ansible_connection": "ssh", "ansible_host": "invalid.example"}}}}}}
            inventory = temp / "hosts.yml"
            inventory.write_text(yaml.safe_dump(inv, sort_keys=False))
            for check in ([], ["--check", "--diff"]):
                for intent in ({}, {"live_preflight_enabled": True}, {"pull_timer_enabled": True},
                               {"adopted": True}):
                    result = subprocess.run(["ansible-playbook", "-i", str(inventory), "fleet.yml",
                                             "-e", json.dumps(intent)] + check, cwd=ROOT, env=env,
                                            capture_output=True, text=True)
                    output = result.stdout + result.stderr
                    if intent:
                        self.assertNotEqual(result.returncode, 0, output)
                        self.assertIn("refused", output)
                    else:
                        self.assertEqual(result.returncode, 0, output)
                        self.assertIn("not converged", output)
                    self.assertFalse(sentinel.exists(), output)
                for role in ("worker", "coordinator", "preflight"):
                    play = temp / "direct.yml"
                    play.write_text(yaml.safe_dump([{"name": "Synthetic direct guard", "hosts": "all",
                        "gather_facts": False, "roles": [role]}]))
                    direct_env = dict(env, ANSIBLE_ROLES_PATH=str(ROOT / "roles"))
                    result = subprocess.run(["ansible-playbook", "-i", str(inventory), str(play),
                        "-e", '{"live_preflight_enabled": true}'] + check, cwd=ROOT, env=direct_env,
                        capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("unfinished", (result.stdout + result.stderr).lower())
                    self.assertFalse(sentinel.exists())

    def test_missing_runner_refusal(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache-ci") as temp:
            temp = Path(temp)
            sentinel = temp / "ssh-called"
            ssh = temp / "ssh"
            ssh.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 97\n")
            ssh.chmod(0o700)
            env = dict(os.environ, ANSIBLE_SSH_EXECUTABLE=str(ssh))
            for runner in (None, {"hosts": {}}):
                for role in ("worker", "coordinator"):
                    for check in ([], ["--check", "--diff"]):
                        for intent in ({}, {"live_preflight_enabled": True},
                                       {"pull_timer_enabled": True}, {"adopted": True}):
                            children = {"fleet_targets": {"hosts": {
                                "synthetic_local": {"ansible_connection": "local", "adopted": False,
                                    "desired_role": "worker", "desired_order": 1},
                                "synthetic_remote": {"ansible_connection": "ssh", "adopted": True,
                                    "desired_role": role, "desired_order": 2,
                                    "ansible_host": "invalid.example"}}}}
                            if runner is not None:
                                children["pull_runner"] = runner
                            inventory = temp / "hosts.yml"
                            inventory.write_text(yaml.safe_dump({"all": {"children": children}}))
                            result = subprocess.run(["ansible-playbook", "-i", str(inventory),
                                "fleet.yml", "-e", json.dumps(intent)] + check,
                                cwd=ROOT, env=env, capture_output=True, text=True)
                            output = result.stdout + result.stderr
                            with self.subTest(runner=runner, role=role, check=check, intent=intent):
                                self.assertNotEqual(result.returncode, 0, output)
                                self.assertIn("refused", output)
                                self.assertFalse(sentinel.exists(), output)

    def test_observation_schema_mutations(self):
        for key, values in {
            "observed_hostname": [None, "", 1, "ambiguous identity"],
            "observed_state_path_candidates": [None, [], "/absolute/state.db",
                ["relative/ambiguous"], [1], ["/"], ["/state/../state.db"],
                ["/state/./state.db"], ["/state//state.db"], ["/state\\bad"],
                ["/state\nbad"]],
        }.items():
            for value in values:
                bad = copy.deepcopy(self.inventory)
                h = bad["all"]["children"]["fleet_targets"]["hosts"][next(iter(self.hosts))]
                if value is None:
                    del h[key]
                else:
                    h[key] = value
                with self.subTest(key=key, value=value), self.assertRaises((AssertionError, KeyError)):
                    inventory_valid(bad)
        for service in ("t3-steward.service", "t3-steward-worker.service"):
            for value in (None, "/absolute/state.db", ["relative/ambiguous"], [1],
                          ["/"], ["/state/../state.db"], ["/state/./state.db"],
                          ["/state//state.db"], ["/state\\bad"], ["/state\nbad"]):
                bad = copy.deepcopy(self.inventory)
                fds = bad["all"]["children"]["fleet_targets"]["hosts"][next(iter(self.hosts))]["observed_open_state_database_fds"]
                if value is None:
                    del fds[service]
                else:
                    fds[service] = value
                with self.subTest(service=service, value=value), self.assertRaises((AssertionError, KeyError)):
                    inventory_valid(bad)
        valid = copy.deepcopy(self.inventory)
        h = valid["all"]["children"]["fleet_targets"]["hosts"][next(iter(self.hosts))]
        h["observed_state_path_candidates"] = ["/candidate/state.db"]
        h["observed_open_state_database_fds"] = {
            "t3-steward.service": ["/runtime/state.db", "/runtime/state.db-wal"],
            "t3-steward-worker.service": []}
        inventory_valid(valid)

    def test_wrapper_resource_limits(self):
        keys = ("ANSIBLE_FORKS", "GOMAXPROCS", "GOFLAGS", "MAKEFLAGS", "CARGO_BUILD_JOBS")
        command = ["bash", "tools/with-ci-env.sh", "python3", "-c",
                   "import json, os; print(json.dumps({k: os.environ[k] for k in " + repr(keys) + "}))"]
        cases = ({}, dict(zip(keys, ("1", "1", "-p=1", "-j1", "1"))),
                 dict(zip(keys, ("1", "1", "-race -p=1", "-j1 --keep-going", "1"))))
        for incoming in cases:
            env = {k: v for k, v in os.environ.items() if k not in keys}
            env.update(incoming)
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = incoming or dict(zip(keys, ("1", "1", "-p=1", "-j1", "1")))
            with self.subTest(incoming=incoming):
                self.assertEqual(json.loads(result.stdout.splitlines()[-1]), expected)

    def test_optimized_bootstrap_mismatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache-ci") as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / "tools", temp / "tools")
            lock = (ROOT / "requirements-ci.txt").read_text()
            (temp / "requirements-ci.txt").write_text(lock.replace("ansible-core==2.19.14", "ansible-core==0.0.0"))
            bin_ = temp / ".venv-ci/bin"
            bin_.mkdir(parents=True)
            for tool in ("python", "python3", "ansible-playbook", "ansible-lint"):
                script = bin_ / tool
                script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
                script.chmod(0o700)
            (temp / ".venv-ci/lock.sha256").write_text(
                hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest())
            for optimize in ("0", "1", "2"):
                result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp,
                    env=dict(os.environ, PYTHONOPTIMIZE=optimize), capture_output=True, text=True)
                with self.subTest(optimize=optimize):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("ansible-core", result.stderr)
            # Simulate a wrong bootstrap interpreter, then a wrong existing venv interpreter.
            (temp / "requirements-ci.txt").write_text(lock)
            (temp / ".venv-ci/lock.sha256").write_text(
                hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest())
            wrong_python = temp / "wrong-python"
            wrong_python.write_text(f"#!{sys.executable}\nimport sys\nsys.version_info = (0, 0, 0)\n"
                "exec(sys.argv[2] if sys.argv[1:] and sys.argv[1] == '-c' else sys.stdin.read())\n")
            wrong_python.chmod(0o700)
            for stage in ("bootstrap", "venv"):
                env = dict(os.environ, PYTHONOPTIMIZE="1", CI_PYTHON=sys.executable)
                if stage == "bootstrap":
                    env["CI_PYTHON"] = str(wrong_python)
                else:
                    shutil.copy(wrong_python, bin_ / "python")
                result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp,
                    env=env, capture_output=True, text=True)
                with self.subTest(stage=stage):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Python version mismatch", result.stderr)

    def test_environment_reuse_and_failures(self):
        lock = (ROOT / "requirements-ci.txt").read_text()
        for line in lock.splitlines():
            if line and not line.startswith("#"):
                self.assertRegex(line, r"^[\w.-]+==[\d.]+ --hash=sha256:[0-9a-f]{64}$")
                name, version = line.split(" --hash=")[0].split("==")
                self.assertEqual(metadata.version(name), version)
        command = ["env", "-u", "VIRTUAL_ENV", "-u", "PYTHONPATH", "bash",
                   "tools/with-ci-env.sh", "python3", "-c", "import sys; print(sys.prefix)"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(ROOT / ".venv-ci"), result.stdout)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache-ci") as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / "tools", temp / "tools")
            shutil.copy(ROOT / "requirements-ci.txt", temp)
            env = dict(os.environ, CI_PYTHON="/bin/false")
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, env=env)
            self.assertNotEqual(result.returncode, 0)
            # Local fake venv tests failure propagation without network or shared changes.
            (temp / ".venv-ci/bin").mkdir(parents=True)
            python = temp / ".venv-ci/bin/python"
            python.write_text("#!/bin/sh\nexit 73\n")
            python.chmod(0o700)
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 73)  # installer failure
            digest = hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest()
            (temp / ".venv-ci/lock.sha256").write_text(digest)
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 73)  # version verifier failure
            python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Missing local executable", result.stderr)
            (temp / "requirements-ci.txt").write_text(lock.replace("ansible-core==2.19.14", "ansible-core==0.0.0"))
            (temp / ".venv-ci/lock.sha256").write_text(hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest())
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Distribution version mismatch: ansible-core", result.stderr)


if __name__ == "__main__":
    unittest.main()
