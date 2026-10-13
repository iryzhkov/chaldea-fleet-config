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


# Exact approved same-version wheel set; independent of the parsed lock.
APPROVED_WHEELS = {
    "ansible-compat==26.10.0": {"700f0778fbb348daf6ee58941871e8ca77a987702993e8bf7895761d036d6450"},
    "ansible-core==2.19.14": {"d518d0e96fa75bedfe9b0a96d5b158aa712d092961824c115140c8677b88ff06"},
    "ansible-lint==26.10.0": {"eaf427a800a65312f4446c33e53d531ddca1d81b82915a3a07dadc79160ec9dc"},
    "attrs==26.1.0": {"c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309"},
    "black==26.10.1": {"03c0ddd93bb392e71209903a691767eb366fe1a76deb9509ccbaae9e1f14bb52", "28842f9a8207cc1df6eb983a35a14c5a0dfcd603d214fe82d84bef552afd2e3a"},
    "bracex==3.1": {"52002b8455658c21f3b6e5eb0f662b57ec9085f42709e58bc86eeab5bc4c37d7"},
    "cffi==2.1.1": {"a931079504ecc49efed7744c476a5c343a92fabf66dec2db95edb1b2fdc770e2", "f16c709686a78c727bbbf059f92b0bf41c6fc60deec706d2dc19f529175a6125"},
    "click==8.5.0": {"255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360"},
    "cryptography==50.0.2": {"9dab55f57c74c3cad24c323bacbbd04be4705ba6eb0d92e920b1fc4837ed5079", "87e9ce85beb6b328ba370cc6e6aea483c92617b4c95b1d33a49297eb662bfb04"},
    "distro==1.9.0": {"7bffd925d65168f85027d8da9af6bddab658135b840670a223589bc0c8ef02b2"},
    "filelock==4.1.1": {"3f4a557945a7b0f95efeb1f432267affe5d45ac8ddde2aed1b97ebb62382c089"},
    "jinja2==3.1.6": {"85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67"},
    "jsonschema-specifications==2025.9.1": {"98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe"},
    "jsonschema==4.26.0": {"d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce"},
    "markupsafe==3.0.4": {"434139499bb20b502ed3baa1f169e618f924a97e7a777fea1a49446d80106cf6", "7018d4af1cd272e847aa5917983ab5e83e4f6579f9dbfecd4a79c0ca80b144c2"},
    "mypy-extensions==1.1.0": {"1be4cccdb0f2482337c4743e60421de3a356cd97508abadd57d47403e94f5505"},
    "packaging==26.3": {"d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"},
    "pathspec==1.1.1": {"a00ce642f577bf7f473932318056212bc4f8bfdf53128c78bbd5af0b9b20b189"},
    "platformdirs==4.13.0": {"3dbcf4cd708f21cf876c4eaa90e58412bc4f033d87143f41b1493ff77c25b7e1"},
    "pycparser==3.11": {"51d5a8ba2be0bbe440b99d2112604c95bbbc3c2748a64260186c541e1729cd80"},
    "pytokens==0.4.1": {"29d1d8fb1030af4d231789959f21821ab6325e463f0503a61d204343c9b355d1", "5502408cab1cb18e128570f8d598981c68a50d0cbd7c61312a90507cd3a1276f"},
    "pyyaml==6.0.3": {"0f29edc409a6392443abf94b9cf89ce99889a1dd5376d94316ae5145dfedd5d6", "ee2922902c45ae8ccada2c5b501ab86c36525b883eff4255313a253a3160861c"},
    "referencing==0.37.0": {"381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231"},
    "resolvelib==1.2.1": {"fb06b66c8da04172d9e72a21d7d06186d8919e32ae5ab5cdf5b9d920be805ac2"},
    "rpds-py==2026.9.1": {"7868b85224291c6cb6759f9b5adb9745f486d226f62b16a614dd5a2a5ab2b35b", "457866b85daf5034296666168b84a69e0b2e89dc4f1af102b46f6448a60b9063"},
    "ruamel.yaml==0.19.1": {"27592957fedf6e0b62f281e96effd28043345e0e66001f97683aa9a40c667c93"},
    "subprocess-tee==0.4.2": {"21942e976715af4a19a526918adb03a8a27a8edab959f2d075b777e3d78f532d"},
    "wcmatch==11.1": {"2863afee97a7dd62e64f7feada864848c1a5e31cb331b3aa530fa1300d2d5d3c"},
    "yamllint==1.38.0": {"fc394a5b3be980a4062607b8fdddc0843f4fa394152b6da21722f5d59013c220"},
}


def lock_valid(text):
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        assert re.fullmatch(r"[\w.-]+==[\d.]+(?: --hash=sha256:[0-9a-f]{64})+", line)
        pin, *tokens = line.split(" ")
        assert pin not in result
        hashes = [token.removeprefix("--hash=sha256:") for token in tokens]
        assert len(set(hashes)) == len(hashes)
        result[pin] = set(hashes)
    assert result == APPROVED_WHEELS


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
        self.assertEqual(plays[0]["hosts"], "all")
        self.assertTrue(plays[0]["any_errors_fatal"])
        for task in plays[0]["tasks"]:
            self.assertIn("ansible.builtin.assert", task)
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
        self.assertEqual(Path(executable).parent, ROOT / "artifacts/.venv-ci/bin")
        result = subprocess.run([executable, "-i", "inventory/hosts.yml", "--syntax-check", "fleet.yml"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_refusal(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
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
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
            temp = Path(temp)
            sentinel = temp / "ssh-called"
            ssh = temp / "ssh"
            ssh.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 97\n")
            ssh.chmod(0o700)
            env = dict(os.environ, ANSIBLE_SSH_EXECUTABLE=str(ssh))
            for runner in (None, {"hosts": {}}):
                for role in ("worker", "coordinator"):
                    for check in ([], ["--check", "--diff"]):
                        for limit in ([], ["--limit", "all"]):
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
                                    "fleet.yml", "-e", json.dumps(intent)] + check + limit,
                                    cwd=ROOT, env=env, capture_output=True, text=True)
                                output = result.stdout + result.stderr
                                with self.subTest(runner=runner, role=role, check=check, limit=limit, intent=intent):
                                    self.assertNotEqual(result.returncode, 0, output)
                                    self.assertIn("refused", output)
                                    self.assertFalse(sentinel.exists(), output)

    def test_disabled_topology_and_valid_runner_matrix(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
            temp = Path(temp)
            sentinel = temp / "ssh-called"
            ssh = temp / "ssh"
            ssh.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 97\n")
            ssh.chmod(0o700)
            env = dict(os.environ, ANSIBLE_SSH_EXECUTABLE=str(ssh))
            for runner in ("valid", "missing", "empty"):
                for role in ("worker", "coordinator"):
                    for check in ([], ["--check", "--diff"]):
                        for limit in ([], ["--limit", "all"]):
                            intents = ({}, {"live_preflight_enabled": True},
                                       {"pull_timer_enabled": True}, {"adopted": True}) if runner == "valid" else ({},)
                            for intent in intents:
                                hosts = {
                                    "synthetic_local": {"ansible_connection": "local", "adopted": False,
                                        "desired_role": "worker", "desired_order": 1},
                                    "synthetic_remote": {"ansible_connection": "ssh", "adopted": False,
                                        "desired_role": role, "desired_order": 2,
                                        "ansible_host": "invalid.example"}}
                                # Only remote host carries intent: selected local vars must not mask it.
                                hosts["synthetic_remote"].update(intent)
                                children = {"fleet_targets": {"hosts": hosts}}
                                if runner != "missing":
                                    children["pull_runner"] = {"hosts": {"synthetic_local": {}} if runner == "valid" else {}}
                                inventory = temp / "hosts.yml"
                                inventory.write_text(yaml.safe_dump({"all": {"children": children}}))
                                result = subprocess.run(["ansible-playbook", "-i", str(inventory), "fleet.yml"] + check + limit,
                                    cwd=ROOT, env=env, capture_output=True, text=True)
                                output = result.stdout + result.stderr
                                with self.subTest(runner=runner, role=role, check=check, limit=limit, intent=intent):
                                    if runner == "valid" and not intent:
                                        self.assertEqual(result.returncode, 0, output)
                                        self.assertIn("not converged", output)
                                    else:
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
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / "tools", temp / "tools")
            lock = (ROOT / "requirements-ci.txt").read_text()
            (temp / "requirements-ci.txt").write_text(lock.replace("ansible-core==2.19.14", "ansible-core==0.0.0"))
            bin_ = temp / "artifacts/.venv-ci/bin"
            bin_.mkdir(parents=True)
            for tool in ("python", "python3", "ansible-playbook", "ansible-lint"):
                script = bin_ / tool
                script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
                script.chmod(0o700)
            (temp / "artifacts/.venv-ci/lock.sha256").write_text(
                hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest())
            for optimize in ("0", "1", "2"):
                result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp,
                    env=dict(os.environ, PYTHONOPTIMIZE=optimize, CI_PYTHON=sys.executable), capture_output=True, text=True)
                with self.subTest(optimize=optimize):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("ansible-core", result.stderr)
            # Simulate a wrong bootstrap interpreter, then a wrong existing venv interpreter.
            (temp / "requirements-ci.txt").write_text(lock)
            (temp / "artifacts/.venv-ci/lock.sha256").write_text(
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

    def test_lock_mutations(self):
        lock = (ROOT / "requirements-ci.txt").read_text()
        lock_valid(lock)
        pin, hashes = next(iter(APPROVED_WHEELS.items()))
        digest = next(iter(hashes))
        line = pin + " --hash=sha256:" + digest
        for bad in (lock.replace(line, pin), lock.replace(digest, "bad"),
                    lock.replace(line, line + " --hash=sha256:" + digest),
                    lock.replace(digest, "0" * 64), lock + line + "\n",
                    lock.replace(pin, pin.split("==")[0] + "==0.0.0"),
                    "\n".join(lock.splitlines()[:-1])):
            with self.subTest(lock=bad), self.assertRaises(AssertionError):
                lock_valid(bad)

    def test_provisioning_failure_boundaries(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / "tools", temp / "tools")
            shutil.copy(ROOT / "requirements-ci.txt", temp)
            stubs = temp / "stubs"
            stubs.mkdir()
            def stub(name, body):
                path = stubs / name
                path.write_text("#!/bin/bash\n" + body + "\n")
                path.chmod(0o700)
            stub("python3.13", "exit 1")
            env = dict(os.environ, PATH=str(stubs) + ":" + os.environ["PATH"])
            env.pop("CI_PYTHON", None)
            command = ["bash", "tools/bootstrap-ci.sh"]
            prefix = temp / "artifacts/.cache-ci/python-3.13.5"
            for override in ("/nonexistent/synthetic-python", "/bin/false"):
                result = subprocess.run(command, cwd=temp, env=dict(env, CI_PYTHON=override), capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(prefix.exists())
            prefix.mkdir(parents=True)
            for receipt in (None, "partial"):
                if receipt:
                    (prefix / "complete").write_text(receipt)
                result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("receipt", result.stderr)
            shutil.rmtree(prefix)
            for tool, body, message in (
                    ("uname", "echo unsupported", "Unsupported native platform"),
                    ("getconf", "echo 'glibc 2.33'", "Requires glibc"),
                    ("getconf", "echo musl", "Requires glibc"),
                    ("make", "echo non-GNU", "Requires GNU make"),
                    ("cc", "exit 72", "Missing native"),
                    ("curl", "exit 74", ""),
                    ("sha256sum", "exit 75", "archive hash mismatch")):
                stub(tool, body)
                if tool == "sha256sum":
                    stub("curl", "exit 0")
                result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
                with self.subTest(boundary=tool):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertFalse((prefix / "complete").exists())
                (stubs / tool).unlink()
                if tool == "sha256sum":
                    (stubs / "curl").unlink()
            # A missing required tool must fail before retrieval, even with other tools present.
            missing = temp / "missing-tool.sh"
            missing.write_text('command() { if [[ "$*" == "-v pkg-config" ]]; then return 1; fi; builtin command "$@"; }\n')
            result = subprocess.run(command, cwd=temp, env=dict(env, BASH_ENV=str(missing)), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing build prerequisite: pkg-config", result.stderr)
            # A genuinely corrupt archive is checked by the real sha256sum.
            stub("curl", 'printf corrupt > "$PWD/artifacts/.cache-ci/python-build/Python-3.13.5.tar.xz"')
            result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("archive hash mismatch", result.stderr)
            (stubs / "curl").unlink()
            # A completed receipt still cannot authorize a wrong local executable.
            prefix.mkdir(parents=True)
            config = f"--prefix={prefix} --with-ensurepip=install --disable-test-modules"
            digest = "93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640"
            (prefix / "complete").write_text(f"{digest}|3.13.5|{os.uname().machine}|{config}|COMPILEALL_OPTS=-j1\n")
            (prefix / "bin").mkdir()
            wrong_local = prefix / "bin/python3.13"
            wrong_local.write_text("#!/bin/sh\nexit 79\n")
            wrong_local.chmod(0o700)
            result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 79)
            shutil.rmtree(prefix)
            # Downstream failure fixtures stub the authenticated download/extraction boundary.
            stub("curl", "exit 0")
            stub("sha256sum", "exit 0")
            stub("tar", 'mkdir -p "$PWD/artifacts/.cache-ci/python-build/Python-3.13.5"')
            build = temp / "artifacts/.cache-ci/python-build/Python-3.13.5"
            build.mkdir(parents=True, exist_ok=True)
            configure = build / "configure"
            for stage in ("configure", "build", "install", "compileall"):
                configure.write_text("#!/bin/sh\nexit " + ("76" if stage == "configure" else "0") + "\n")
                configure.chmod(0o700)
                stub("make", 'if [[ "$1" == --version ]]; then echo "GNU Make"; exit 0; fi\n' +
                     ('exit 77' if stage == "build" else '[[ "$1" != install ]] || exit 78'))
                if stage == "compileall":
                    fake_python = f'#!/bin/bash\n[[ "$1" != -m ]] || exit 80\nexec "{sys.executable}" "$@"\n'
                    stub("make", 'if [[ "$1" == --version ]]; then echo "GNU Make"; exit 0; fi\n' +
                        f'mkdir -p "{prefix}/bin"\n' +
                        f"cat > '{prefix}/bin/python3.13' <<'PYTHON'\n" + fake_python +
                        f"PYTHON\nchmod +x '{prefix}/bin/python3.13'")
                result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True)
                with self.subTest(stage=stage):
                    self.assertEqual(result.returncode, {"configure": 76, "build": 77, "install": 78, "compileall": 80}[stage])
                    self.assertFalse((prefix / "complete").exists())
            # Missing capability and unsupported ABI are rejected even for explicit exact Python.
            for injection, message in (
                    ("sysconfig.get_config_var = lambda key: 1", "Unsupported Python ABI"),
                    ("platform.machine = lambda: 'unsupported'", "Unsupported Python architecture"),
                    ("sys.modules['ssl'] = None", "ssl")):
                wrong = temp / "synthetic-python"
                wrong.write_text(f"#!{sys.executable}\nimport sys, sysconfig, platform\n" +
                    injection + "\nsys.argv = sys.argv[1:]\nexec(sys.stdin.read())\n")
                wrong.chmod(0o700)
                result = subprocess.run(command, cwd=temp, env=dict(env, CI_PYTHON=str(wrong)), capture_output=True, text=True)
                with self.subTest(injection=injection):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)

    def test_environment_reuse_and_failures(self):
        lock = (ROOT / "requirements-ci.txt").read_text()
        lock_valid(lock)
        for line in lock.splitlines():
            if line and not line.startswith("#"):
                self.assertRegex(line, r"^[\w.-]+==[\d.]+(?: --hash=sha256:[0-9a-f]{64})+$")
                name, version = line.split(" --hash=")[0].split("==")
                self.assertEqual(metadata.version(name), version)
        command = ["env", "-u", "VIRTUAL_ENV", "-u", "PYTHONPATH", "bash",
                   "tools/with-ci-env.sh", "python3", "-c", "import sys; print(sys.prefix)"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(ROOT / "artifacts/.venv-ci"), result.stdout)
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts/.cache-ci") as temp:
            temp = Path(temp)
            shutil.copytree(ROOT / "tools", temp / "tools")
            shutil.copy(ROOT / "requirements-ci.txt", temp)
            env = dict(os.environ, CI_PYTHON="/bin/false")
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, env=env)
            self.assertNotEqual(result.returncode, 0)
            # Local fake venv tests failure propagation without network or shared changes.
            (temp / "artifacts/.venv-ci/bin").mkdir(parents=True)
            python = temp / "artifacts/.venv-ci/bin/python"
            python.write_text("#!/bin/sh\nexit 73\n")
            python.chmod(0o700)
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, env=dict(os.environ, CI_PYTHON=sys.executable), capture_output=True)
            self.assertEqual(result.returncode, 73)  # installer failure
            digest = hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest()
            (temp / "artifacts/.venv-ci/lock.sha256").write_text(digest)
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 73)  # version verifier failure
            python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Missing local executable", result.stderr)
            (temp / "requirements-ci.txt").write_text(lock.replace("ansible-core==2.19.14", "ansible-core==0.0.0"))
            (temp / "artifacts/.venv-ci/lock.sha256").write_text(hashlib.sha256((temp / "requirements-ci.txt").read_bytes()).hexdigest())
            result = subprocess.run(["bash", "tools/bootstrap-ci.sh"], cwd=temp, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Distribution version mismatch: ansible-core", result.stderr)


if __name__ == "__main__":
    unittest.main()
