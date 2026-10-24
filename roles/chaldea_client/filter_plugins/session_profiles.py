"""Closed public validation of fixed provider profiles. No filesystem, credentials or network.

A profile names already-installed official binaries by explicit path, SHA-256 and
size, and the protected preset whose enrollment authorizes its single HTTP MCP
server. A Codex profile also names a private profile HOME by path only. The role
renders the launcher and public files from this data; nothing here is inferred
from a target file. Each driver has its own exact field set.
"""
import re
from collections.abc import Mapping
from posixpath import normpath

from ansible.errors import AnsibleFilterError

FIELDS = {"driver", "native", "host", "catalog", "elf_machine", "model", "home", "tmpdir", "cwd",
          "preset", "audience", "server", "url", "tools", "disabled_servers"}
PINS = ("native", "host", "catalog")
CLAUDE_FIELDS = {"driver", "native", "elf_machine", "cwd", "preset", "audience", "server", "url", "tools"}
# The Claude launcher streams at most this many native bytes.
CLAUDE_NATIVE_LIMIT = 400000000
# The Claude launcher denies these T3 control server names in its permissions.
CLAUDE_RESERVED_SERVERS = {"t3-code", "t3_code"}
NAME = r"[a-z0-9][a-z0-9-]{0,47}"
PATH = r"/([A-Za-z0-9._@+-]+/)*[A-Za-z0-9._@+-]+"
SERVER = r"[A-Za-z0-9_-]{1,64}"
TOOL = r"[a-z][a-z0-9_]{0,63}"
URL = r"https://[a-z0-9]([a-z0-9-]*[a-z0-9])?([.][a-z0-9]([a-z0-9-]*[a-z0-9])?)*(/[A-Za-z0-9._~-]+)*/?"
# Codex reads at most 64 KiB of these public files; ELFs keep a generous 2 GiB ceiling.
LIMITS = {"native": 1 << 31, "host": 1 << 31, "catalog": 65536}
# Only the two machines the fleet runs: x86-64 and AArch64.
MACHINES = {62, 183}


def require(condition, field):
    if not condition:
        raise AnsibleFilterError("Fixed provider profile refused: " + field)


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value, re.ASCII) is not None


def safe_path(value, field):
    require(matches(value, PATH) and normpath(value) == value
            and all(part not in {".", ".."} for part in value.split("/")[1:]), field)


def under(value, parent, field):
    safe_path(value, field)
    require(value.startswith(parent + "/"), field + " must be inside the fleet home")


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def unique_list(value, minimum, maximum, pattern, field):
    require(isinstance(value, list) and minimum <= len(value) <= maximum, field)
    require(all(matches(v, pattern) for v in value) and len(set(value)) == len(value), field)


def pin(value, limit, field):
    require(isinstance(value, Mapping) and set(value) == {"source", "sha256", "size"},
            field + " needs exactly source, sha256 and size")
    safe_path(value["source"], field + ".source")
    require(matches(value["sha256"], r"[0-9a-f]{64}"), field + ".sha256")
    require(integer(value["size"]) and 0 < value["size"] <= limit, field + ".size")


def granted_actions(preset, audience):
    """Actions of legacy {audience, grants} services; None when the form has no grant list."""
    services = [s for s in preset.get("services", []) if isinstance(s, Mapping) and s.get("audience") == audience]
    if len(services) != 1:
        return set(), False
    grants = services[0].get("grants")
    if grants is None:
        return None, True
    actions = set()
    for grant in grants if isinstance(grants, list) else []:
        if isinstance(grant, Mapping) and isinstance(grant.get("actions"), list):
            actions.update(a for a in grant["actions"] if isinstance(a, str))
    return actions, True


def codex_profile(field, value, presets, fleet_home):
    require(set(value) == FIELDS, field + " needs exactly the codex profile fields")
    for kind in PINS:
        pin(value[kind], LIMITS[kind], field + "." + kind)
    require(value["native"]["source"] != value["host"]["source"], field + " native and host sources differ")
    require(integer(value["elf_machine"]) and value["elf_machine"] in MACHINES, field + ".elf_machine")
    require(matches(value["model"], r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"), field + ".model")
    under(value["home"], fleet_home, field + ".home")
    # The interactive operator's own Codex home is never a profile home.
    require(value["home"] != fleet_home, field + ".home must differ from the fleet home")
    under(value["tmpdir"], fleet_home, field + ".tmpdir")
    # The launcher requires os.getcwd() to equal cwd exactly: the T3 server's
    # working directory, which is the fleet home itself or a directory in it.
    safe_path(value["cwd"], field + ".cwd")
    require(value["cwd"] == fleet_home or value["cwd"].startswith(fleet_home + "/"),
            field + ".cwd must be the fleet home or inside it")
    preset_id = value["preset"]
    require(isinstance(preset_id, str) and preset_id in presets, field + ".preset must be a declared preset")
    preset = presets[preset_id]
    require(isinstance(preset, Mapping) and preset.get("model") == value["model"],
            field + ".model must equal its preset model")
    unique_list(value["disabled_servers"], 0, 16, SERVER, field + ".disabled_servers")
    require(value["server"] not in value["disabled_servers"], field + ".server cannot also be disabled")


def claude_profile(field, value):
    require(set(value) == CLAUDE_FIELDS, field + " needs exactly the claude profile fields")
    pin(value["native"], CLAUDE_NATIVE_LIMIT, field + ".native")
    require(integer(value["elf_machine"]) and value["elf_machine"] in MACHINES, field + ".elf_machine")
    safe_path(value["cwd"], field + ".cwd")
    require(value["server"] not in CLAUDE_RESERVED_SERVERS, field + ".server cannot be a T3 control server name")


def profile(name, value, presets, enrollments, fleet_home):
    field = "profile " + name
    require(isinstance(value, Mapping) and value.get("driver") in {"codex", "claude"},
            field + ".driver must be codex or claude")
    if value["driver"] == "codex":
        codex_profile(field, value, presets, fleet_home)
    else:
        claude_profile(field, value)
    preset_id = value["preset"]
    require(isinstance(preset_id, str) and preset_id in presets, field + ".preset must be a declared preset")
    preset = presets[preset_id]
    require(isinstance(preset, Mapping), field + ".preset must be a declared preset")
    require(matches(value["audience"], r"[a-z][a-z0-9-]{0,31}"), field + ".audience")
    actions, present = granted_actions(preset, value["audience"])
    require(present, field + ".audience must name exactly one preset service")
    require(preset_id in enrollments and isinstance(enrollments[preset_id], Mapping),
            field + " needs an enrollment for its preset")
    require(matches(value["url"], URL) and enrollments[preset_id].get("resource") == value["url"],
            field + ".url must equal its enrollment resource")
    require(matches(value["server"], SERVER), field + ".server")
    unique_list(value["tools"], 1, 16, TOOL, field + ".tools")
    require(actions is None or set(value["tools"]) <= actions, field + ".tools must be granted preset actions")


def retired(value, fleet_home):
    """A retired Codex profile is exactly {name, home}; a Claude one is exactly {name, driver: claude}."""
    require(isinstance(value, Mapping) and set(value) in ({"name", "home"}, {"name", "driver"}),
            "retired profile needs exactly name and home, or name and driver claude")
    require(matches(value["name"], NAME), "retired profile name")
    if "driver" in value:
        require(value["driver"] == "claude", "retired profile driver must be claude")
        return
    under(value["home"], fleet_home, "retired profile " + value["name"] + ".home")
    require(value["home"] != fleet_home, "retired profile home must differ from the fleet home")


def chaldea_session_profiles(profiles, presets, enrollments, fleet_home, absent):
    require(isinstance(profiles, Mapping) and len(profiles) <= 8, "at most eight profiles")
    require(isinstance(absent, list) and len(absent) <= 8, "at most eight retired profiles")
    if not profiles and not absent:
        return True
    safe_path(fleet_home, "fleet home")
    presets = presets if isinstance(presets, Mapping) else {}
    enrollments = enrollments if isinstance(enrollments, Mapping) else {}
    for name, value in profiles.items():
        require(matches(name, NAME), "profile name")
        profile(name, value, presets, enrollments, fleet_home)
    homes = [v["home"] for v in profiles.values() if v["driver"] == "codex"]
    require(len(set(homes)) == len(homes), "profile homes must be distinct")
    for value in absent:
        retired(value, fleet_home)
    names = [v["name"] for v in absent]
    require(len(set(names)) == len(names), "retired profile names must be distinct")
    require(not set(names) & set(profiles), "a profile cannot be delivered and retired together")
    retired_homes = {v["home"] for v in absent if "home" in v}
    require(not set(homes) & retired_homes, "delivered and retired Codex profile homes must be disjoint")
    return True


class FilterModule:
    def filters(self):
        return {"chaldea_session_profiles": chaldea_session_profiles}
