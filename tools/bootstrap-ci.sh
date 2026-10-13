#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PIP_CACHE_DIR="$ROOT/artifacts/.cache-ci/pip" TMPDIR="$ROOT/artifacts/.cache-ci/tmp"
mkdir -p "$TMPDIR"
export MAKEFLAGS="${MAKEFLAGS:--j1}"
ARCH=$(uname -m)
[[ $(uname -s) == Linux && "$ARCH" =~ ^(x86_64|aarch64)$ ]] || { echo "Unsupported native platform" >&2; exit 1; }
LIBC=$(getconf GNU_LIBC_VERSION)
[[ "$LIBC" =~ ^glibc\ ([0-9]+)\.([0-9]+)$ ]] &&
  (( BASH_REMATCH[1] > 2 || (BASH_REMATCH[1] == 2 && BASH_REMATCH[2] >= 34) )) ||
  { echo "Requires glibc >=2.34: $LIBC" >&2; exit 1; }
PREFIX="$ROOT/artifacts/.cache-ci/python-3.13.5"
SOURCE_SHA=93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640
CONFIG="--prefix=$PREFIX --with-ensurepip=install --disable-test-modules"
RECEIPT="$SOURCE_SHA|3.13.5|$ARCH|$CONFIG|COMPILEALL_OPTS=-j1"
validate_python() {
  "$1" - "$ARCH" <<'PY'
import platform, struct, sys, sysconfig
if sys.version_info[:3] != (3, 13, 5):
    raise SystemExit("Python version mismatch: " + sys.version)
if platform.python_implementation() != "CPython" or sysconfig.get_config_var("Py_GIL_DISABLED"):
    raise SystemExit("Unsupported Python ABI")
if platform.machine() != sys.argv[1] or platform.system() != "Linux":
    raise SystemExit("Unsupported Python architecture")
multiarch = sys.argv[1] + "-linux-gnu"
if (struct.calcsize("P") != 8 or sysconfig.get_config_var("SIZEOF_VOID_P") != 8 or
        sysconfig.get_config_var("MULTIARCH") != multiarch or
        sysconfig.get_config_var("SOABI") != "cpython-313-" + multiarch):
    raise SystemExit("Unsupported Python ABI")
import ssl, venv, ensurepip, ctypes, zlib, bz2, lzma, sqlite3
# The fixed CPython source supplies ensurepip 25.1.1, including packaging.
# Read its wheel before installation; do not require a new bootstrap dependency.
if ensurepip.version() != "25.1.1":
    raise SystemExit("Unsupported ensurepip tag provider")
with ensurepip._get_pip_whl_path_ctx() as wheel:
    sys.path.insert(0, str(wheel))
    from pip._vendor.packaging.tags import sys_tags
    supported = {(tag.interpreter, tag.abi, tag.platform) for tag in sys_tags()}
    sys.path.pop(0)
required = {
    ("cp313", "cp313", "manylinux_2_17_" + sys.argv[1]),
    ("cp313", "cp313", "manylinux_2_28_" + sys.argv[1]),
    ("cp311", "abi3", "manylinux_2_34_" + sys.argv[1]),
    ("py3", "none", "any"),
}
if not required <= supported:
    raise SystemExit("Unsupported Python wheel tags")
if ssl.OPENSSL_VERSION_INFO < (1, 1, 1):
    raise SystemExit("Requires OpenSSL >=1.1.1")
PY
}
if [[ ${CI_PYTHON+x} ]]; then
  PYTHON="$CI_PYTHON"
elif [[ -e "$PREFIX" ]]; then
  [[ -f "$PREFIX/complete" && $(< "$PREFIX/complete") == "$RECEIPT" ]] ||
    { echo "Incomplete or mismatched local Python receipt" >&2; exit 1; }
  PYTHON="$PREFIX/bin/python3.13"
elif command -v python3.13 >/dev/null && python3.13 -c 'import sys; sys.exit(sys.version_info[:3] != (3, 13, 5))'; then
  PYTHON=python3.13
else
  for tool in cc make pkg-config curl sha256sum tar xz; do
    command -v "$tool" >/dev/null || { echo "Missing build prerequisite: $tool" >&2; exit 1; }
  done
  [[ $(make --version) == GNU\ Make* ]] || { echo "Requires GNU make" >&2; exit 1; }
  BUILD="$ROOT/artifacts/.cache-ci/python-build"
  mkdir -p "$BUILD"
  [[ $(df -Pk "$BUILD" | awk 'NR==2 {print $4}') -ge 1048576 ]] ||
    { echo "Requires 1 GiB free task storage" >&2; exit 1; }
  cat > "$BUILD/probe.c" <<'C'
#include <openssl/ssl.h>
#include <ffi.h>
#include <zlib.h>
#include <bzlib.h>
#include <lzma.h>
#include <sqlite3.h>
#include <stdatomic.h>
#if OPENSSL_VERSION_NUMBER < 0x10101000L
#error OpenSSL >=1.1.1 required
#endif
int main(void) {
  ffi_cif cif; ffi_prep_cif(&cif, FFI_DEFAULT_ABI, 0, &ffi_type_void, 0);
  SSL_CTX *ctx = SSL_CTX_new(TLS_method()); SSL_CTX_free(ctx);
  (void)zlibVersion(); (void)BZ2_bzlibVersion(); (void)lzma_version_number();
  (void)sqlite3_libversion(); _Atomic unsigned long long x = 0;
  (void)atomic_fetch_add(&x, 1); return 0;
}
C
  ATOMIC=()
  [[ "$ARCH" != aarch64 ]] || ATOMIC=(-latomic)
  cc -std=c11 "$BUILD/probe.c" -o "$BUILD/probe" -lssl -lcrypto -lffi -lz -lbz2 -llzma -lsqlite3 "${ATOMIC[@]}" ||
    { echo "Missing native OpenSSL/libffi/compression/sqlite/atomic build prerequisite" >&2; exit 1; }
  ARCHIVE="$BUILD/Python-3.13.5.tar.xz"
  curl --fail --location --proto '=https' --proto-redir '=https' --output "$ARCHIVE" https://www.python.org/ftp/python/3.13.5/Python-3.13.5.tar.xz
  printf '%s  %s\n' "$SOURCE_SHA" "$ARCHIVE" | sha256sum --check --status ||
    { echo "Python source archive hash mismatch" >&2; exit 1; }
  tar -xJf "$ARCHIVE" -C "$BUILD"
  (
    cd "$BUILD/Python-3.13.5"
    ./configure --prefix="$PREFIX" --with-ensurepip=install --disable-test-modules
    make
    make install COMPILEALL_OPTS=-j1
  )
  PYTHON="$PREFIX/bin/python3.13"
  validate_python "$PYTHON"
  "$PYTHON" -m compileall -q -j1 "$PREFIX/lib/python3.13"
  printf '%s\n' "$RECEIPT" > "$PREFIX/complete"
fi
validate_python "$PYTHON"
LOCK=$("$PYTHON" -c 'import hashlib; print(hashlib.sha256(open("requirements-ci.txt","rb").read()).hexdigest())')
if [[ ! -d artifacts/.venv-ci ]]; then
  "$PYTHON" -m venv artifacts/.venv-ci
fi
validate_python artifacts/.venv-ci/bin/python
if [[ ! -f artifacts/.venv-ci/lock.sha256 ]] || [[ $(< artifacts/.venv-ci/lock.sha256) != "$LOCK" ]]; then
  artifacts/.venv-ci/bin/python -m pip --isolated install --cache-dir "$PIP_CACHE_DIR" --disable-pip-version-check --require-hashes --only-binary=:all: -r requirements-ci.txt
fi
artifacts/.venv-ci/bin/python - <<'PY'
import importlib.metadata as m
import pathlib
import sys
if sys.version_info[:3] != (3, 13, 5):
    raise SystemExit("Python version mismatch: " + sys.version)
for line in pathlib.Path("requirements-ci.txt").read_text().splitlines():
    if line and not line.startswith("#"):
        name, version = line.split(" --hash=")[0].split("==")
        installed = m.version(name)
        if installed != version:
            raise SystemExit(f"Distribution version mismatch: {name}: {installed} != {version}")
print("Verified Python", sys.version.split()[0], "and all locked distributions")
PY
artifacts/.venv-ci/bin/python -m pip --isolated check
for tool in python3 ansible-playbook ansible-lint; do
  test -x "artifacts/.venv-ci/bin/$tool" || { echo "Missing local executable: $tool" >&2; exit 1; }
done
printf '%s\n' "$LOCK" > artifacts/.venv-ci/lock.sha256
