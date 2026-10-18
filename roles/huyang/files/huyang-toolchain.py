#!/usr/bin/env python3
"""Install a checksum-pinned, isolated Huyang toolchain. No host package manager."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import posixpath
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from typing import Any

SERVERS = {
    "go": ("gopls", "gopls", "go"),
    "rust": ("rust_analyzer", "rust-analyzer", "rust"),
    "python": ("pyright", "pyright-langserver", "python"),
    "typescript": ("ts_ls", "typescript-language-server", "typescript"),
    "javascript": ("ts_ls", "typescript-language-server", "javascript"),
    "java": ("jdtls", "jdtls", "java"),
    "cpp": ("clangd", "clangd", "cpp"),
    "c": ("clangd", "clangd", "c"),
    "bash": ("bashls", "bash-language-server", "sh"),
}
EXTRA_PARSERS = ("lua", "json", "yaml", "toml", "markdown", "markdown_inline",
                 "vim", "vimdoc", "query")
NPM_LANGUAGES = {"python", "typescript", "javascript", "bash"}


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def selected_parsers(languages):
    return sorted(set(languages) | set(EXTRA_PARSERS) |
                  ({"tsx"} if "typescript" in languages else set()))


def validate_pins(pins, architecture, languages):
    if architecture not in ("x86_64", "aarch64") or pins.get("schema") != 1:
        raise ValueError("unsupported architecture or pin schema")
    if not languages or len(set(languages)) != len(languages) or set(languages) - SERVERS.keys():
        raise ValueError("select unique languages from the strict nine-language list")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", pins.get("gopls", "")):
        raise ValueError("gopls needs an exact version")
    # Validate both architectures, including inputs not selected on this host.
    for group in [pins["shared"], pins["parsers"], *pins["architectures"].values()]:
        for name, pin in group.items():
            url = urllib.parse.urlsplit(pin["url"])
            if (url.scheme != "https" or not url.netloc or url.username or url.password or
                    not pin.get("version") or
                    not re.fullmatch(r"[a-f0-9]{64}", pin.get("sha256", "")) or
                    pin["sha256"] == "0" * 64 or
                    pin.get("format") not in ("tar", "zip", "gzip") or
                    pin.get("strip") not in (0, 1)):
                raise ValueError("invalid reviewed artifact pin: " + name)
    if set(pins["architectures"]) != {"x86_64", "aarch64"}:
        raise ValueError("pins must cover x86_64 and aarch64")
    for name in selected_parsers(languages):
        pin = pins["parsers"][name]
        safe_name(pin["location"] or ".")
        for filename in pin["files"]:
            safe_name(filename)



def managed_directory(path, create=False):
    """Refuse symlinks in every existing ancestor instead of resolving them."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("managed directory must be absolute without '..': " + str(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if create:
                current.mkdir(mode=0o700)
                info = current.lstat()
            else:
                continue
        if current.exists() and (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)):
            raise ValueError("managed directory is a symlink or non-directory: " + str(current))
        if current.is_symlink():
            raise ValueError("managed directory is a symlink: " + str(current))


def regular_input(path):
    managed_directory(path.parent)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("input/receipt must be a regular file: " + str(path))


def discard_tree(path):
    if path.is_symlink():
        raise ValueError("refusing cleanup through a symlink: " + str(path))
    if path.exists():
        # Go's default module cache can contain read-only directories even after
        # a failed build. Never chmod through a symlink while removing scratch.
        for directory, _, _ in os.walk(path, followlinks=False):
            os.chmod(directory, 0o700)
        shutil.rmtree(path)


def installed_manifest(stage):
    """Describe all installed code/data and safe internal links, excluding receipt."""
    root_mode = stat.S_IMODE(stage.lstat().st_mode)
    if root_mode & 0o7022:
        raise ValueError("unsafe installed release directory mode")
    manifest = {".": {"kind": "directory", "mode": root_mode}}
    for directory, directories, files in os.walk(stage, followlinks=False):
        for name in sorted(directories + files):
            path = Path(directory) / name
            relative = path.relative_to(stage).as_posix()
            if relative == "receipt.json":
                continue
            info = path.lstat()
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                if PurePosixPath(target).is_absolute() or "\\" in target or "\0" in target:
                    raise ValueError("unsafe installed symlink: " + relative)
                normalized = posixpath.normpath((Path(relative).parent / target).as_posix())
                safe_name(normalized)
                # Validate chains too, not just a link's immediate destination.
                try:
                    path.resolve(strict=True).relative_to(stage)
                except (OSError, ValueError, RuntimeError) as error:
                    raise ValueError("unsafe installed symlink: " + relative) from error
                manifest[relative] = {"kind": "symlink", "target": target, "mode": mode}
            elif stat.S_ISREG(info.st_mode):
                if mode & 0o7022:
                    raise ValueError("unsafe installed file mode: " + relative)
                manifest[relative] = {"kind": "file", "sha256": digest(path), "mode": mode}
            elif stat.S_ISDIR(info.st_mode):
                if mode & 0o7022:
                    raise ValueError("unsafe installed directory mode: " + relative)
                manifest[relative] = {"kind": "directory", "mode": mode}
            else:
                raise ValueError("unsafe installed special node: " + relative)
    return manifest


def receipt_bytes(receipt):
    return (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()


def check_installed_manifest(stage, receipt):
    managed_directory(stage)
    regular_input(stage / "receipt.json")
    if stat.S_IMODE((stage / "receipt.json").lstat().st_mode) != 0o600:
        raise ValueError("installed receipt mode mismatch")
    if (stage / "receipt.json").read_bytes() != receipt_bytes(receipt):
        raise ValueError("installed receipt hash mismatch")
    actual = installed_manifest(stage)
    expected = receipt["files"]
    for path in sorted(expected.keys() - actual.keys()):
        raise ValueError("installed manifest missing path: " + path)
    for path in sorted(actual.keys() - expected.keys()):
        raise ValueError("installed manifest has unlisted path: " + path)
    for path in sorted(expected):
        if actual[path] != expected[path]:
            raise ValueError("installed manifest hash/type/mode mismatch: " + path)


def fetch(pin, cache):
    """Verify cached bytes too. Never fetch a digest from the network."""
    managed_directory(cache, create=True)
    path = cache / pin["sha256"]
    if path.is_file() and not path.is_symlink() and digest(path) == pin["sha256"]:
        return path
    if path.exists() or path.is_symlink():
        path.unlink()
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=cache)
    try:
        print("huyang-toolchain: downloading " + pin["url"], file=sys.stderr, flush=True)
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(pin["url"], timeout=120) as response:
            if urllib.parse.urlsplit(response.url).scheme != "https":
                raise ValueError("download redirected away from HTTPS")
            shutil.copyfileobj(response, out, 1024 * 1024)
        if digest(temporary) != pin["sha256"]:
            raise ValueError("SHA256 mismatch: " + pin["url"])
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or "\0" in name:
        raise ValueError("unsafe archive path: " + name)
    return path


def archive_path(name, strip):
    parts = safe_name(name).parts
    return Path(*parts[strip:]) if len(parts) > strip else None


def unpack(archive, destination, pin, keep=None):
    """Reject traversal, special nodes, and writes through archive-created links."""
    managed_directory(destination, create=True)
    if pin["format"] == "gzip":
        raise ValueError("raw gzip is an executable, not an archive")
    is_zip = pin["format"] == "zip"
    opener = zipfile.ZipFile if is_zip else tarfile.open
    with opener(archive) as opened:
        # tarfile and zipfile expose different member/reader protocols.
        source: Any = opened
        member: Any
        entries = []
        for member in source.infolist() if is_zip else source.getmembers():
            name = member.filename if is_zip else member.name
            path = archive_path(name, pin["strip"])
            mode = member.external_attr >> 16 if is_zip else member.mode
            link = stat.S_ISLNK(mode) if is_zip else member.issym() or member.islnk()
            directory = member.is_dir() if is_zip else member.isdir()
            regular = not directory and not link if is_zip else member.isfile()
            if is_zip and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
                raise ValueError("unsafe archive special node: " + name)
            if not (directory or regular or link):
                raise ValueError("unsafe archive special node: " + name)
            if path is None:
                continue
            if link:
                target = source.read(member).decode() if is_zip else member.linkname
                if PurePosixPath(target).is_absolute() or "\\" in target or "\0" in target:
                    raise ValueError("unsafe archive link: " + target)
                if not is_zip and member.islnk():
                    target_path = archive_path(target, pin["strip"])
                else:
                    target_path = Path(posixpath.normpath((path.parent / target).as_posix()))
                    safe_name(target_path.as_posix())
                if target_path is None:
                    raise ValueError("invalid archive link")
            else:
                target_path = None
            entries.append((member, path, mode, link, directory, target_path))
        links = {path for _, path, _, link, _, _ in entries if link}
        seen = set()
        for _, path, _, _, _, _ in entries:
            if any(parent in links for parent in path.parents):
                raise ValueError("unsafe archive entry below symlink: " + str(path))
            if path in seen:
                raise ValueError("duplicate archive path: " + str(path))
            seen.add(path)
        # Write regular entries before links so links can never redirect writes.
        for member, path, mode, link, directory, _ in entries:
            if link or (keep and not keep(path)):
                continue
            target = destination / path
            if directory:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = source.open(member) if is_zip else source.extractfile(member)
            if stream is None:
                raise ValueError("missing archive file contents")
            with stream, target.open("xb") as out:
                shutil.copyfileobj(stream, out, 1024 * 1024)
            target.chmod(0o755 if mode & 0o111 else 0o644)
        for member, path, _, link, _, target_path in entries:
            if not link or (keep and not keep(path)):
                continue
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not is_zip and member.islnk():
                os.link(destination / target_path, target)
            else:
                os.symlink(os.path.relpath(destination / target_path, target.parent), target)


def run(argv, env, cwd=None):
    subprocess.run([str(arg) for arg in argv], env=env, cwd=cwd, check=True,
                   stdout=sys.stderr, stderr=sys.stderr, timeout=1800)


def symlink(stage, name, target):
    path = stage / "bin" / name
    path.symlink_to(os.path.relpath(stage / target, path.parent))


def wrapper(stage, name, command, environment=""):
    path = stage / "bin" / name
    path.write_text('#!/bin/sh\nset -eu\n'
                    'base=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)\n'
                    'export PATH="$base/bin:/usr/bin:/bin"\n' + environment +
                    "exec " + command + ' "$@"\n')
    path.chmod(0o755)


def build(stage, root, pins, architecture, languages, inputs):
    artifacts = pins["architectures"][architecture]
    env = dict(os.environ)
    env.update(HOME=str(stage / "home"), TMPDIR=str(stage / "tmp"),
               XDG_CACHE_HOME=str(stage / "cache"), HUYANG_FRICTION="0",
               ZIG_GLOBAL_CACHE_DIR=str(stage / "cache/zig"))
    for name in ("home", "tmp", "cache", "bin", "runtime/parser"):
        (stage / name).mkdir(parents=True, exist_ok=True)
    # These write targets are all under the fresh installation stage, never the
    # caller's home. Normal service state is separately owned under root/state.
    assert Path(env["HOME"]) == stage / "home"
    env["PATH"] = str(stage / "bin") + ":/usr/bin:/bin"
    for directory in ("CONFIG", "DATA", "CACHE", "STATE"):
        env["XDG_" + directory + "_HOME"] = str(stage / "home" / directory.lower())
    env["NPM_CONFIG_USERCONFIG"] = "/dev/null"
    env["npm_config_update_notifier"] = "false"

    def install(name, shared=False, destination=None, keep=None):
        pin = pins["shared"][name] if shared else artifacts[name]
        dest = stage / (destination or name)
        unpack(fetch(pin, root / "downloads"), dest, pin, keep)
        return dest

    install("nvim")
    symlink(stage, "nvim", "nvim/bin/nvim")
    install("zig")
    install("lspconfig", shared=True)
    install("python")
    # Isolated Python probes ignore PYTHON* environment variables. Force -B in
    # PATH launchers, and prepare all stdlib optimization variants before sealing
    # for probes that subsequently invoke sys.executable directly.
    run([stage / "python/bin/python3", "-B", "-m", "compileall", "-q", "-j", "2",
         "-o", "0", "-o", "1", "-o", "2", "-x", r"(^|/)(test|tests)/",
         stage / "python/lib"], env)
    for executable in ("python3", "python"):
        wrapper(stage, executable, '"$base/python/bin/python3" -B')
    if set(languages) & NPM_LANGUAGES:
        install("node")
        symlink(stage, "node", "node/bin/node")
        npm = stage / "npm"
        npm.mkdir()
        shutil.copyfile(inputs / "huyang-toolchain-package.json", npm / "package.json")
        shutil.copyfile(inputs / "huyang-toolchain-package-lock.json", npm / "package-lock.json")
        lock = json.loads((npm / "package-lock.json").read_text())
        for name, package in lock["packages"].items():
            if name and (not package.get("integrity", "").startswith("sha512-") or
                         not package.get("resolved", "").startswith("https://registry.npmjs.org/")):
                raise ValueError("npm lock contains an unverified dependency: " + name)
        run([stage / "node/bin/node", stage / "node/lib/node_modules/npm/bin/npm-cli.js",
             "ci", "--prefix", npm, "--ignore-scripts", "--no-audit", "--no-fund",
             "--cache", stage / "cache/npm"], env)
        for language, script in (("python", "pyright-langserver"),
                                 ("typescript", "typescript-language-server"),
                                 ("javascript", "typescript-language-server"),
                                 ("bash", "bash-language-server")):
            if language in languages:
                wrapper(stage, script, '"$base/npm/node_modules/.bin/' + script + '"')
    if "go" in languages:
        install("go")
        symlink(stage, "go", "go/bin/go")
        goenv = dict(env, GOBIN=str(stage / "bin"), GOPATH=str(stage / "gopath"),
                     GOCACHE=str(stage / "cache/go"), GOMODCACHE=str(stage / "gopath/pkg/mod"),
                     GOTOOLCHAIN="local", GOPROXY="https://proxy.golang.org",
                     GOSUMDB="sum.golang.org", GOPRIVATE="", GONOSUMDB="", GONOPROXY="",
                     GOENV="off", GOFLAGS="-modcacherw", CGO_ENABLED="0")
        run([stage / "bin/go", "install", "golang.org/x/tools/gopls@" + pins["gopls"]], goenv)
    if "rust" in languages:
        rust = stage / "rust"
        rust.mkdir()
        for component in ("rustc", "cargo", "rust-std"):
            extracted = install(component)
            payload = extracted / (component if component != "rust-std"
                                   else "rust-std-" + architecture + "-unknown-linux-gnu")
            shutil.copytree(payload, rust, dirs_exist_ok=True, symlinks=True)
        install("rust_src", shared=True)
        for executable in ("rustc", "cargo"):
            symlink(stage, executable, "rust/bin/" + executable)
        pin = artifacts["rust_analyzer"]
        with gzip.GzipFile(filename=fetch(pin, root / "downloads"), mode="rb") as source:
            analyzer = stage / "rust-analyzer"
            with analyzer.open("wb") as output:
                shutil.copyfileobj(source, output)
            analyzer.chmod(0o755)
        wrapper(stage, "rust-analyzer", '"$base/rust-analyzer"',
                'export RUST_SRC_PATH="$base/rust_src/rust-src/lib/rustlib/src/rust/library"\n')
    if set(languages) & {"c", "cpp"}:
        def clangd_keep(path):
            name = path.as_posix()
            return (name == "bin/clangd" or name.startswith("lib/clang/") or
                    (name.startswith("lib/") and ".so" in path.name))
        install("clangd", keep=clangd_keep)
        wrapper(stage, "clangd", '"$base/clangd/bin/clangd"',
                'export LD_LIBRARY_PATH="$base/clangd/lib"\n')
    if "bash" in languages:
        install("shellcheck")
        symlink(stage, "shellcheck", "shellcheck/shellcheck")
    if "java" in languages:
        install("jdk")
        install("jdtls", shared=True)
        symlink(stage, "java", "jdk/bin/java")
        wrapper(stage, "jdtls", '"$base/jdtls/bin/jdtls"',
                'export JAVA_HOME="$base/jdk"\n')
    for language in selected_parsers(languages):
        pin = pins["parsers"][language]
        source = stage / "sources" / language
        unpack(fetch(pin, root / "downloads"), source, pin)
        working = source / pin["location"]
        # Sources already contain generated C and scanner files. No npm, Git
        # submodule, parser generator, system compiler or online headers.
        run([stage / "zig/zig", "cc", "-shared", "-fPIC", "-O2", "-Isrc",
             *pin["files"], "-o", stage / "runtime/parser" / (language + ".so")], env, working)
    config = {
        "languages": languages, "parsers": selected_parsers(languages),
        "servers": {language: dict(zip(("config", "executable", "filetype"), SERVERS[language]))
                    for language in languages},
        "state_root": str(root / "state"),
    }
    (stage / "config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    shutil.copyfile(inputs / "headless-init.lua", stage / "headless-init.lua")
    # Keep cache/downloads outside the immutable runtime; discard build-only trees.
    for name in ("home", "tmp", "cache", "sources", "gopath", "zig",
                 "rustc", "cargo", "rust-std"):
        discard_tree(stage / name)
    return config


def verify(stage, receipt):
    check_installed_manifest(stage, receipt)
    config = json.loads((stage / "config.json").read_text())
    for language, server in config["servers"].items():
        executable = stage / "bin" / server["executable"]
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("missing executable for " + language + ": " + str(executable))
        if not (stage / "lspconfig/lsp" / (server["config"] + ".lua")).is_file():
            raise ValueError("missing lspconfig for " + language)
    for parser in config["parsers"]:
        if not (stage / "runtime/parser" / (parser + ".so")).is_file():
            raise ValueError("missing parser: " + parser)
    with tempfile.TemporaryDirectory(prefix=".verify-", dir=stage.parent) as scratch:
        home = Path(scratch) / "home"
        home.mkdir()
        env = dict(os.environ, HOME=str(home), TMPDIR=scratch, HUYANG_FRICTION="0",
                   PATH=str(stage / "bin") + ":/usr/bin:/bin",
                   HUYANG_TOOLCHAIN_VERIFY="1")
        assert Path(env["HOME"]) == home
        for directory in ("CONFIG", "DATA", "CACHE", "STATE"):
            env["XDG_" + directory + "_HOME"] = str(home / directory.lower())
        script = Path(scratch) / "verify.lua"
        script.write_text("""
local ok, err = pcall(function()
  assert(vim.version().api_level >= 13, "Neovim API < 13")
  local cfg = vim.g.huyang_fleet_config
  for _, parser in ipairs(cfg.parsers) do
    assert(vim.treesitter.language.add(parser), "cannot load parser " .. parser)
    vim.treesitter.language.inspect(parser)
    vim.treesitter.get_string_parser("", parser):parse()
  end
  for _, server in pairs(cfg.servers) do
    assert(type(vim.lsp.config[server.config]) == "table", "missing config " .. server.config)
    assert(vim.fn.executable(server.executable) == 1, "missing server " .. server.executable)
  end
end)
if not ok then io.stderr:write(tostring(err) .. "\\n"); vim.cmd("cquit 1") end
vim.cmd("qa!")
""")
        run([stage / "bin/nvim", "--headless", "--clean", "-u", stage / "headless-init.lua",
             "-l", script], env)
    return config


def release_key(pins, architecture, languages, inputs):
    h = hashlib.sha256(json.dumps([pins, architecture, sorted(languages)],
                                 sort_keys=True).encode())
    for path in (Path(__file__), inputs / "huyang-toolchain-package.json",
                 inputs / "huyang-toolchain-package-lock.json", inputs / "headless-init.lua"):
        h.update(path.read_bytes())
    return h.hexdigest()


def install_toolchain(root, pins, architecture, languages, inputs):
    validate_pins(pins, architecture, languages)
    managed_directory(root, create=True)
    for name in ("releases", "downloads", "receipts", "state", "inputs"):
        managed_directory(root / name, create=True)
    managed_directory(inputs)
    for name in ("huyang-toolchain-package.json", "huyang-toolchain-package-lock.json", "headless-init.lua"):
        regular_input(inputs / name)
    releases = root / "releases"
    key = release_key(pins, architecture, languages, inputs)
    target = releases / key
    authority = root / "receipts" / (key + ".json")
    lock_path = root / ".install.lock"
    if lock_path.exists() or lock_path.is_symlink():
        regular_input(lock_path)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = root / "current"
        if current.exists() or current.is_symlink():
            if not current.is_symlink() or not re.fullmatch(r"releases/[a-f0-9]{64}", os.readlink(current)):
                raise ValueError("current must be a safe managed release symlink")
            managed_directory(root / os.readlink(current))
        if target.exists() or target.is_symlink():
            managed_directory(target)
            regular_input(authority)
            if stat.S_IMODE(authority.lstat().st_mode) != 0o600:
                raise ValueError("authoritative receipt mode mismatch")
            receipt = json.loads(authority.read_text())
            if (receipt["release"] != key or receipt["architecture"] != architecture or
                    sorted(receipt["languages"]) != sorted(languages) or receipt["pins"] != pins):
                raise ValueError("authoritative receipt identity mismatch")
            verify(target, receipt)
            if current.is_symlink() and os.readlink(current) == "releases/" + key:
                return {"changed": False, "release": key}
        else:
            temporary = Path(tempfile.mkdtemp(prefix=".build-", dir=releases))
            try:
                build(temporary, root, pins, architecture, languages, inputs)
                receipt = {"release": key, "architecture": architecture, "languages": languages,
                           "pins": pins, "files": installed_manifest(temporary)}
                (temporary / "receipt.json").write_bytes(receipt_bytes(receipt))
                (temporary / "receipt.json").chmod(0o600)
                verify(temporary, receipt)
                temporary.rename(target)
                # An independent receipt outside executable content is the local
                # baseline. A release cannot authenticate its own edited manifest.
                if authority.exists() or authority.is_symlink():
                    regular_input(authority)
                receipt_fd, pending_receipt = tempfile.mkstemp(prefix=".receipt-", dir=root / "receipts")
                try:
                    with os.fdopen(receipt_fd, "wb") as output:
                        output.write(receipt_bytes(receipt))
                    os.replace(pending_receipt, authority)
                finally:
                    Path(pending_receipt).unlink(missing_ok=True)
            finally:
                if temporary.exists():
                    discard_tree(temporary)
        pending = root / ".current-new"
        pending.unlink(missing_ok=True)
        pending.symlink_to("releases/" + key)
        os.replace(pending, current)
        return {"changed": True, "release": key}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--languages", required=True, help="JSON array")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="validate only, without writes/network")
    args = parser.parse_args()
    managed_directory(args.root)
    regular_input(args.pins)
    pins = json.loads(args.pins.read_text())
    languages = json.loads(args.languages)
    if not args.root.is_absolute() or args.root == Path("/"):
        parser.error("--root must be an absolute dedicated directory")
    validate_pins(pins, args.architecture, languages)
    if args.check:
        result = {"changed": False, "would_install": True, "languages": languages}
    else:
        result = install_toolchain(args.root, pins, args.architecture, languages, args.inputs)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
