# Huyang fleet toolchain

The Huyang role is off by default. Its toolchain task runs only inside the parent's
enabled-role gate. Nothing in this component enables a host, manages the service,
installs Huyang itself, or changes personal Neovim configuration.

## Role interface

Toolchain defaults belong to defaults/main.yml, so host inventory retains
precedence for language selections. The parent imports tasks/lspconfig.yml after
the role's enabled gate.

The default huyang_languages list is exactly:
go, rust, python, typescript, javascript, java, cpp, c, bash. This matches Huyang's
README Requirements, cmd/huyang/langprobe_test.go, and tests/langprobe-chaldea.sh
at source commit c1a942e. For example, a smaller host can use:

~~~yaml
huyang_languages: [go, python, typescript, javascript, cpp, c, bash]
~~~

The default huyang_toolchain_root is
"{{ fleet_home }}/.local/share/huyang-toolchain". The task exports these facts:

| Fact | Value |
| --- | --- |
| huyang_toolchain_bin | root/current/bin |
| huyang_headless_init | root/current/headless-init.lua |
| huyang_java_home | root/current/jdk when Java is selected, otherwise empty |
| huyang_expected_language_servers | Selected subset of huyang_toolchain_servers |
| huyang_toolchain_changed | True only when the verified current symlink changes |

The parent supplies PATH with huyang_toolchain_bin, HUYANG_HEADLESS_INIT with
huyang_headless_init, and JAVA_HOME when nonempty. The parent restarts only when
the Huyang release pin changes. Toolchain and configuration changes stage for the
next pin-driven restart; huyang_toolchain_changed alone does not restart it.
This task emits no restart or handler notification.

| Language | lspconfig | PATH executable | Status filetype |
| --- | --- | --- | --- |
| go | gopls | gopls | go |
| rust | rust_analyzer | rust-analyzer | rust |
| python | pyright | pyright-langserver | python |
| typescript | ts_ls | typescript-language-server | typescript |
| javascript | ts_ls | typescript-language-server | javascript |
| java | jdtls | jdtls | java |
| cpp | clangd | clangd | cpp |
| c | clangd | clangd | c |
| bash | bashls | bash-language-server | sh |

The parent health fixture should contain valid project markers and a source file for
each selected language. Request their Status filetype values explicitly with
language_server_status.languages to start incidental servers too. Require a healthy
provider through workspace_inspect, then inspect each selected filetype separately.
Converge fails only on a missing required server: a missing language row,
unconfigured status, or missing expected server name. Accept configured starting,
not_started and capacity-delay responses that name the expected server. Installer
verification checks executable/config presence and parser loading separately.
This component's private scratch smoke requires real attachment and diagnostics
for every selected language; that stronger smoke criterion is not the converge gate.

Huyang's install.lua scans lsp/*.lua on runtimepath and chooses executable commands.
The fleet init supplies the pinned nvim-lspconfig runtime and selected PATH wrappers,
then enables the selected configurations. It sets runtimepath and packpath explicitly.
It loads no personal init, plugins, Mason, or package directory. Runtime LSP state
uses root/state; installation verification uses a throwaway HOME and XDG directories.

## Reviewed inputs

Exact URLs, versions, and SHA256 values live in
inventory/group_vars/all/huyang-toolchain.yml. Inventory loads alongside
inventory/group_vars/all/main.yml. The installer refuses missing pins, unsupported
architectures and non-HTTPS artifact URLs. It fetches no checksums during installation.

Pins acquired on 2026-10-17:

| Input | Pin and provenance |
| --- | --- |
| Neovim | 0.12.5, official neovim/neovim GitHub release digests, x64 and arm64 |
| nvim-lspconfig | 19576de1c1b6d1b5e231ea6ef9cba9a811c322bb, SHA256 of codeload archive |
| Go / gopls | Go 1.27.0 official dl.google.com SHA256; gopls v0.23.0 built with sum.golang.org verification |
| Node | 26.12.0, official nodejs.org/dist/v26.12.0/SHASUMS256.txt |
| npm servers | pyright 1.1.413, typescript-language-server 6.0.0, TypeScript 6.0.3, bash-language-server 5.6.0 |
| rust-analyzer | 2026-09-07, official rust-lang/rust-analyzer GitHub release digests |
| Rust prerequisites | rustc, cargo, rust-std, rust-src 1.99.0, static.rust-lang.org published SHA256 files |
| clangd | 22.1.6, official clangd/clangd x64 zip; official llvm/llvm-project LLVM Linux ARM64 archive |
| ShellCheck | v0.11.0, official koalaman/shellcheck release digests |
| Java | Temurin JDK 21.0.12.1+1, official adoptium/temurin21-binaries release digests and checksum files |
| jdtls | 1.60.0-202606262232, download.eclipse.org/jdtls/milestones/1.60.0 archive and published SHA256 |
| Python | CPython 3.13.16+20261013, astral-sh/python-build-standalone release digests, install_only_stripped glibc builds |
| Parser compiler | Zig 0.15.2, ziglang.org/download/index.json SHA256 and official distribution archives |

The x64 Neovim, lspconfig, rust-analyzer, rust-src, clangd, ShellCheck, Java and
jdtls pins agree with Huyang's langprobe-chaldea.sh. Native arm64 pins were
independently obtained from upstream release metadata and published checksum files.
Node, Go and Rust pins follow the existing fleet job-host checksum pattern and
were independently checked against upstream manifests.

The arm64 clangd input is the official LLVM archive, about 1.77 GB compressed.
Only clangd, shared libraries and clang resource headers are retained. Disabling
both c and cpp avoids this download. Disabling Rust or Java avoids those servers,
their native prerequisites and their language parsers.

npm uses the committed huyang-toolchain-package-lock.json, generated on agent-a
with the exact top-level versions, --before=2026-10-16T00:00:00Z, and install
scripts disabled. Every transitive entry has an exact version, registry tarball
URL and SHA512 integrity. Installation uses npm ci --ignore-scripts; npm checks
the locked integrity. All four npm packages are installed together; only selected
server launchers appear on the toolchain PATH. No npm resolution occurs on hosts.

The gopls build forces GOPROXY=https://proxy.golang.org and GOSUMDB=sum.golang.org,
clears GOPRIVATE/GONOSUMDB/GONOPROXY, sets GOFLAGS=-modcacherw for safe scratch
cleanup, disables automatic Go toolchain downloads, and uses its pinned Go
distribution with CGO disabled.

## Parsers and activation

Parser revisions and download digests are pinned from nvim-treesitter's lockfile at
cf12346a3414fa1b06af75c79faebe7f76df080a, with repository locations and generated
source files verified against its parsers.lua. This includes each selected language,
tsx when TypeScript is selected, and Lua, JSON, YAML, TOML, Markdown, inline Markdown,
Vim, Vimdoc, and Tree-sitter query syntax. No parser generator runs at installation.
Pinned Zig compiles the archive's generated C and scanner sources, including their
vendored headers, into runtime/parser/*.so.

Before Ansible writes inputs, a read-only preflight rejects symlinks in the
managed paths and their ancestors. The installer independently checks root,
releases, inputs, downloads, receipts, state, input files, lock and release paths.
It never silently resolves a managed-directory symlink. The installer verifies
cached archives on every use. It validates tar and zip names,
link destinations, duplicate entries, special nodes and entries below symlinks before
extracting any files. It strips setuid/setgid and world/group write bits. Downloads,
source trees and build commands stay inside the dedicated toolchain root.

A release key covers pins, architecture, selected languages, installer bytes, init and
npm manifests. Build and verification happen in a fresh staging directory. Every
installed file receives a SHA256 in a manifest that also records directory/file modes
and internal symlink targets. Receipt bytes are stored inside the release and as an
independent baseline under root/receipts. Before running an installed binary,
verification compares those receipts and the complete tree. It rejects changed bytes,
changed modes/types/link targets, escaping or dangling links, special nodes, missing
paths and unlisted additions. Runtime state remains separate under root/state.
Verification then checks executable and lspconfig presence, Neovim API level >=13,
and real loading and parsing with every installed Tree-sitter parser. Only a successful release can replace
current, through an atomic symlink rename. Old releases are retained for rollback.
A repeat run verifies the existing release and reports changed=false. A damaged
existing release fails clearly; it does not silently reinstall or switch current.

Check mode validates selection and exposes the service facts. Every directory write,
copy, template, download, install and subprocess task is skipped.

## Tests

Run tests through Chaldea on agent-a with HOME and TMPDIR under disk scratch.
Assert the intended HOME before any mkdir or test write. The local client scratch
is ~/.cache/chaldea-scratch/agent-tooling; a job uses its writable /home/job scratch.
The unit tests also support tools/ci.sh's asserted TMPDIR/fleet-test-home.

tests/test_huyang_toolchain.py covers checksum mismatch, cache corruption,
tar/zip traversal, escaping links, special nodes, writes through symlinks, duplicate
entries, valid internal links, missing servers, idempotence, failed-upgrade rollback,
npm lock integrity, symlinked managed directories and files, installed-code drift,
independent receipts, pre-execution rejection and real Ansible check-mode execution.

For the optional real smoke, stage a hash-verified requirements-ci.txt environment,
then run tests/fixtures/huyang_toolchain_smoke.py --report REPORT.json. It installs
inside scratch, verifies parsers, checks native runtimes, repeats installation, and
opens broken fixtures to require server attachment and diagnostics for every selected
language. It does not contact the installed Huyang service.

Run the same fixture with --architecture aarch64 --archives-only to verify all native
and shared archive digests, archive safety and native ELF machine IDs without running
arm64 code. Return report files with chaldea exec --artifact and retain the job IDs.
