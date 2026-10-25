#!/usr/bin/python
"""Choose fleet-owned mise tools without evaluating user configuration."""

DOCUMENTATION = r"""
module: mise_agent_tools
short_description: Select agent tools not declared in user mise configuration
description:
  - Reads TOML without evaluating templates or exposing configuration values.
  - Uses the installed mise registry in an empty temporary home to identify aliases.
  - Does not modify files or install tools. Requires Python 3.11 or newer.
options:
  home: {description: Fleet user's home, type: path, required: true}
  dropin: {description: Fleet managed drop-in, type: path, required: true}
  tools: {description: Selected tools, type: list, elements: dict, required: true}
"""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

try:
    import tomllib
except ImportError:
    tomllib = None

from ansible.module_utils.basic import AnsibleModule


def read_config(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"{path}: expected a regular TOML file; resolve it before retrying")
    try:
        return tomllib.loads(path.read_text()) if path.exists() else {}
    except (OSError, UnicodeError, ValueError):
        # TOML exceptions can include source lines, including secret values.
        raise ValueError(f"{path}: cannot read valid TOML; repair it before retrying") from None


def registry_groups(scratch):
    with tempfile.TemporaryDirectory(prefix="mise-registry-", dir=scratch) as directory:
        root = Path(directory)
        environment = {"PATH": os.environ.get("PATH", os.defpath), "HOME": directory,
                       "XDG_CONFIG_HOME": str(root / "config"),
                       "XDG_CACHE_HOME": str(root / "cache"),
                       "XDG_DATA_HOME": str(root / "data"),
                       "XDG_STATE_HOME": str(root / "state"),
                       "MISE_SYSTEM_CONFIG_DIR": str(root / "system"),
                       "MISE_CONFIG_DIR": str(root / "config/mise"),
                       "MISE_CEILING_PATHS": directory, "TMPDIR": directory}
        try:
            result = subprocess.run(["mise", "registry", "--json"], cwd=directory,
                                    env=environment, capture_output=True, text=True,
                                    timeout=30, check=True)
            entries = json.loads(result.stdout)
            groups = []
            for entry in entries:
                groups.append(set([entry["short"], *entry.get("aliases", []),
                                   *entry["backends"]]))
            return groups
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
            raise ValueError("Cannot read mise registry in isolation; ensure a compatible mise "
                             "with registry --json is on PATH and retry") from None


def identities(name, groups):
    # Tool options may be encoded in a quoted tool key. Ownership covers the
    # complete tool, regardless of its versions or install options.
    match = re.fullmatch(r"([^\s\[\]{}\"\\]+)(?:\[[^\r\n]*\])?", name)
    if not match:
        raise ValueError("Unsupported tool identity; use a literal mise tool name")
    name = match[1]
    matches = {name}
    # Registry aliases can overlap across entries, so include their closure.
    while True:
        expanded = matches.union(*(group for group in groups if matches & group))
        if expanded == matches:
            break
        matches = expanded
    if len(matches) == 1 and ":" not in name:
        raise ValueError("Unknown shorthand in mise tools; use its explicit backend identifier "
                         "or restore the registry entry before retrying")
    return matches


def select(home, dropin, tools, scratch):
    if tomllib is None:
        raise ValueError("mise_agents requires Python 3.11+ for safe TOML parsing")
    redirects = ("MISE_ENV", "MISE_CONFIG_DIR", "MISE_GLOBAL_CONFIG_FILE",
                 "MISE_CONFIG_FILE", "MISE_OVERRIDE_CONFIG_FILENAMES",
                 "MISE_DEFAULT_CONFIG_FILENAME")
    if any(os.environ.get(key) for key in redirects):
        raise ValueError("Mise configuration environment overrides are active; resolve ownership "
                         "for the normal global config before retrying")
    config = Path(home) / ".config/mise"
    for directory in (Path(home) / ".config", config, config / "conf.d"):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"{directory}: expected a regular configuration directory")
    managed = Path(dropin)
    if managed.parent != config / "conf.d" or managed.suffix != ".toml":
        raise ValueError("mise_agents_dropin must be a TOML file directly under ~/.config/mise/conf.d")
    previous = read_config(managed)
    if set(previous) - {"tools"}:
        raise ValueError(f"{managed}: contains non-tool sections; move user settings out before retrying")

    # These forms can introduce declarations we cannot identify by reading the
    # normal global file and its plain fragments. Do not evaluate user code.
    paths = [config / "config.toml", config / "mise.toml",
             config / "config.local.toml", config / "config.override.toml"]
    fragments = config / "conf.d"
    if fragments.exists():
        for path in sorted(fragments.iterdir()):
            if path.name.startswith(".") or path == managed:
                continue
            if path.is_dir():
                raise ValueError(f"{path}: conf.d folders need an explicit ownership decision before retrying")
            if path.suffix == ".toml":
                paths.append(path)
    declared = []
    for path in paths:
        data = read_config(path)
        if not isinstance(data.get("alias", {}), dict):
            raise ValueError(f"{path}: alias must be a TOML table")
        if (any(key in data for key in ("include", "tool_alias", "plugins")) or
                any(isinstance(value, dict) and "backend" in value
                    for value in data.get("alias", {}).values())):
            raise ValueError(f"{path}: includes or custom tool aliases/plugins need an explicit ownership decision")
        table = data.get("tools", {})
        if not isinstance(table, dict):
            raise ValueError(f"{path}: tools must be a TOML table")
        for value in table.values():
            versions = value if isinstance(value, list) else [value]
            if not versions or any(not (isinstance(version, str) and version or
                                       isinstance(version, dict) and
                                       isinstance(version.get("version"), str) and version["version"])
                                   for version in versions):
                raise ValueError(f"{path}: tools need version strings or version tables")
        declared.extend(table)
    if any(not isinstance(tool.get("name"), str) or
           set(tool) - {"name", "install_options"} or
           ("install_options" in tool and not isinstance(tool["install_options"], str))
           for tool in tools):
        raise ValueError("mise_agents_tools entries need name and optional string install_options")
    if not tools:
        return [], []
    # No user declarations means there is nothing to collide with. Still use the
    # registry for shorthand equivalence between the selected tools themselves.
    groups = registry_groups(scratch)
    user = set().union(*(identities(name, groups) for name in declared))
    selected, overridden, seen = [], [], set()
    for tool in tools:
        names = identities(tool["name"], groups)
        if names & seen:
            raise ValueError("mise_agents_tools contains equivalent tool identities; select each tool once")
        seen.update(names)
        (overridden if names & user else selected).append(tool)
    return selected, overridden


def main():
    module = AnsibleModule(argument_spec={
        "home": {"type": "path", "required": True},
        "dropin": {"type": "path", "required": True},
        "tools": {"type": "list", "elements": "dict", "required": True},
    }, supports_check_mode=True)
    try:
        selected, overridden = select(module.params["home"], module.params["dropin"],
                                      module.params["tools"], module.tmpdir)
    except ValueError as error:
        module.fail_json(msg=str(error))
        return
    module.exit_json(changed=False, tools=selected,
                     overridden=[tool["name"] for tool in overridden])


if __name__ == "__main__":
    main()
