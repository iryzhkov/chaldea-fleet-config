#!/usr/bin/env python3
"""Private job smoke. Never contacts or installs on a live Huyang host."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "roles/huyang"
spec = importlib.util.spec_from_file_location("huyang_toolchain", ROLE / "files/huyang-toolchain.py")
assert spec and spec.loader
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


def assert_scratch():
    home = Path(os.environ["HOME"]).resolve()
    assert "chaldea-scratch/agent-tooling" in str(home)
    assert not str(home).startswith("/tmp/")
    assert "chaldea-scratch/agent-tooling" in str(Path(os.environ["TMPDIR"]).resolve())
    return home


def elf_header(archive, pin, suffix):
    if pin["format"] == "gzip":
        with gzip.GzipFile(filename=archive, mode="rb") as source:
            return source.read(64)
    if pin["format"] == "zip":
        with zipfile.ZipFile(archive) as source:
            name = next(n for n in source.namelist() if n.endswith(suffix))
            with source.open(name) as stream:
                return stream.read(64)
    with tarfile.open(archive) as source:
        member = next(m for m in source.getmembers() if m.isfile() and m.name.endswith(suffix))
        stream = source.extractfile(member)
        assert stream
        with stream:
            return stream.read(64)



def init_only(scratch, pins, architecture):
    stage = scratch / "init-only"
    stage.mkdir(parents=True, exist_ok=True)
    pin = pins["architectures"][architecture]["nvim"]
    manager.unpack(manager.fetch(pin, scratch / "downloads"), stage / "nvim", pin)
    (stage / "lspconfig/lsp").mkdir(parents=True)
    (stage / "lspconfig/lsp/jdtls.lua").write_text("return { cmd = {'true'}, filetypes = {'java'} }\n")
    (stage / "headless-init.lua").write_bytes((ROLE / "templates/headless-init.lua.j2").read_bytes())
    state = stage / "state"
    (stage / "config.json").write_text(json.dumps({
        "state_root": str(state), "languages": ["java"], "parsers": [],
        "servers": {"java": {"config": "jdtls", "executable": "jdtls", "filetype": "java"}},
    }))
    script = stage / "assert-init.lua"
    script.write_text("""
local ok, err = pcall(function()
  dofile(vim.env.HUYANG_INIT_UNDER_TEST)
  local state = vim.g.huyang_fleet_config.state_root
  assert(vim.env.PYTHONDONTWRITEBYTECODE == "1")
  assert(vim.env.TMPDIR == state .. "/tmp")
  assert(vim.fn.isdirectory(vim.env.TMPDIR) == 1)
  assert(vim.env.JDTLS_JVM_ARGS:find("-Djava.io.tmpdir=" .. state .. "/tmp", 1, true))
  assert(vim.env.XDG_CONFIG_HOME == state .. "/nvim/config")
  local configuration = state .. "/jdtls/" .. vim.fs.basename(vim.fs.dirname(vim.env.HUYANG_INIT_UNDER_TEST)) .. "/configuration"
  assert(vim.env.JDTLS_JVM_ARGS:find("-Dosgi.configuration.area=" .. configuration, 1, true))
  assert(vim.fn.isdirectory(configuration) == 1)
end)
if not ok then io.stderr:write(tostring(err) .. "\\n"); vim.cmd("cquit 1") end
vim.cmd("qa!")
""")
    env = dict(os.environ, HUYANG_INIT_UNDER_TEST=str(stage / "headless-init.lua"))
    command = [str(stage / "nvim/bin/nvim"), "--headless", "--clean", "-u", "NONE", "-l", str(script)]
    subprocess.run(command, env=env, check=True, timeout=60)
    (state / "nvim/config").rmdir()
    outside = scratch / "outside-state"
    outside.mkdir()
    (outside / "keep").write_text("unchanged")
    (state / "nvim/config").symlink_to(outside, target_is_directory=True)
    script.write_text("""
local ok, err = pcall(dofile, vim.env.HUYANG_INIT_UNDER_TEST)
if ok or not tostring(err):find("unsafe Huyang state directory", 1, true) then
  io.stderr:write("state symlink was not rejected: " .. tostring(err) .. "\\n")
  vim.cmd("cquit 1")
end
vim.cmd("qa!")
""")
    subprocess.run(command, env=env, check=True, timeout=60)
    assert {path.name for path in outside.iterdir()} == {"keep"}
    assert (outside / "keep").read_text() == "unchanged"
    return {"architecture": architecture, "init_only": True,
            "python_bytecode_disabled": True, "java_tmp_inside_state": True,
            "state_symlink_rejected": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture", default=platform.machine())
    parser.add_argument("--archives-only", action="store_true")
    parser.add_argument("--init-only", action="store_true")
    parser.add_argument("--languages", default=",".join(manager.SERVERS))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    home = assert_scratch()
    scratch = home / ("archive-validation" if args.archives_only else "toolchain-smoke")
    scratch.mkdir(parents=True, exist_ok=True)
    pins = yaml.safe_load((ROOT / "inventory/group_vars/all/huyang-toolchain.yml").read_text())["huyang_toolchain_pins"]
    languages = args.languages.split(",")
    manager.validate_pins(pins, args.architecture, languages)
    if args.init_only:
        assert args.architecture == platform.machine()
        report = init_only(scratch, pins, args.architecture)
    elif args.archives_only:
        # Download/hash both shared and native inputs. Parse native archive
        # metadata without extracting executable payloads or running any code.
        artifacts = pins["architectures"][args.architecture]
        all_pins = {**artifacts, **pins["shared"],
                    **{"parser_" + k: v for k, v in pins["parsers"].items()}}
        def check(item):
            name, pin = item
            archive = manager.fetch(pin, scratch / "downloads")
            if pin["format"] != "gzip":
                out = scratch / "metadata" / name
                manager.unpack(archive, out, pin, keep=lambda _path: False)
            return name, {"sha256": manager.digest(archive), "version": pin["version"]}
        verified = dict(ThreadPoolExecutor(4).map(check, all_pins.items()))
        for name, suffix in {"nvim": "/bin/nvim", "zig": "/zig", "python": "/bin/python3.13",
                             "go": "/bin/go", "node": "/bin/node",
                             "rustc": "/bin/rustc", "cargo": "/bin/cargo",
                             "shellcheck": "/shellcheck", "jdk": "/bin/java",
                             "clangd": "/bin/clangd", "rust_analyzer": ""}.items():
            header = elf_header(scratch / "downloads" / artifacts[name]["sha256"], artifacts[name], suffix)
            assert header[:4] == b"\x7fELF", name
            machine = struct.unpack("<H" if header[5] == 1 else ">H", header[18:20])[0]
            assert machine == (183 if args.architecture == "aarch64" else 62), (name, machine)
            verified[name]["elf_machine"] = machine
        report = {"architecture": args.architecture, "archive_only": True, "verified": verified}
    else:
        assert args.architecture == platform.machine(), "never execute foreign-architecture inputs"
        inputs = scratch / "inputs"
        inputs.mkdir(exist_ok=True)
        for name in ("huyang-toolchain-package.json", "huyang-toolchain-package-lock.json"):
            shutil.copyfile(ROLE / "files" / name, inputs / name)
        shutil.copyfile(ROLE / "templates/headless-init.lua.j2", inputs / "headless-init.lua")
        root = scratch / "root"
        first = manager.install_toolchain(root, pins, args.architecture, languages, inputs)
        second = manager.install_toolchain(root, pins, args.architecture, languages, inputs)
        assert second["changed"] is False
        current = root / "current"
        # Exercise runtime prerequisites, not just server-file presence.
        commands = [["nvim", "--version"], ["python3", "--version"]]
        for language, argv in {
            "go": [["go", "version"], ["gopls", "version"]],
            "rust": [["rustc", "--version"], ["cargo", "--version"], ["rust-analyzer", "--version"]],
            "python": [["pyright-langserver", "--version"]],
            "typescript": [["typescript-language-server", "--version"]],
            "javascript": [["typescript-language-server", "--version"]],
            "java": [["java", "-version"]],
            "c": [["clangd", "--version"]],
            "cpp": [["clangd", "--version"]],
            "bash": [["bash-language-server", "--version"], ["shellcheck", "--version"]],
        }.items():
            if language in languages:
                commands.extend(argv)
        env = dict(os.environ, PATH=str(current / "bin") + ":/usr/bin:/bin")
        versions = {}
        for command in commands:
            # pyright-langserver accepts stdio transport, not --version.
            if command[0] == "pyright-langserver":
                continue
            result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
            assert result.returncode == 0, (command, result.stdout, result.stderr)
            versions[command[0]] = (result.stdout + result.stderr).strip()
        # Real server attachment/diagnostics, in a private Neovim process.
        env["HUYANG_TOOLCHAIN_SMOKE_ROOT"] = str(scratch / "projects")
        subprocess.run([str(current / "bin/nvim"), "--headless", "--clean", "-u",
                        str(current / "headless-init.lua"), "-l",
                        str(ROOT / "tests/fixtures/huyang_toolchain_smoke.lua")],
                       env=env, check=True, timeout=900)
        after_runtime = manager.install_toolchain(root, pins, args.architecture, languages, inputs)
        assert after_runtime["changed"] is False
        report = {"architecture": args.architecture, "first": first, "second": second,
                  "after_runtime": after_runtime, "languages": languages, "versions": versions,
                  "config": json.loads((current / "config.json").read_text())}
    # Report lives in the job worktree solely to return it as an artifact.
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.report), "architecture": args.architecture,
                      "archive_only": args.archives_only}), flush=True)


if __name__ == "__main__":
    main()
