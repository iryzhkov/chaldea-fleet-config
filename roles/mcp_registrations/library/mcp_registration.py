#!/usr/bin/python
"""Register one MCP server with Claude Code or Codex, idempotently."""

DOCUMENTATION = r"""
module: mcp_registration
short_description: Register one MCP server with Claude Code or Codex
description:
  - For Claude Code, reads the user-scope registration with C(claude mcp get)
    and replaces it through C(claude mcp remove) and C(claude mcp add-json -s user)
    when it differs. ~/.claude.json is never edited directly.
  - For Codex, rewrites only the [mcp_servers.NAME] tables of config.toml and
    refuses when the result would change anything else in the file.
  - Environment values never appear in the diff or the result.
options:
  provider: {description: claude or codex, required: true, type: str}
  name: {description: Server name, required: true, type: str}
  state: {description: present or absent, default: present, type: str}
  command: {description: Executable of a stdio server, type: str}
  args: {description: Its arguments, type: list, elements: str}
  env: {description: Environment the server gets, type: dict}
  extra: {description: Further provider-specific keys, type: dict}
  claude_command: {description: The claude CLI as an argument list, type: list, elements: str}
  codex_config: {description: Path of Codex config.toml, type: path}
"""

import json
import os
import re
import tempfile

try:
    import tomllib
except ImportError:  # Python before 3.11
    tomllib = None

from ansible.module_utils.basic import AnsibleModule


def redacted(definition, previous=None):
    """definition with each env value replaced by whether it differs from previous."""
    if definition is None:
        return None
    shown = dict(definition)
    if isinstance(shown.get("env"), dict):
        old = (previous or {}).get("env") or {}
        if previous is None:
            shown["env"] = {key: "<redacted>" for key in shown["env"]}
        else:
            shown["env"] = {key: "<redacted>" if old.get(key) == value else "<redacted, changed>" for key, value in shown["env"].items()}
    return shown


def diff(name, before, after):
    def text(definition):
        return "" if definition is None else json.dumps(definition, indent=2, sort_keys=True) + "\n"

    return {"before_header": name, "after_header": name, "before": text(redacted(before)), "after": text(redacted(after, before or {}))}


# Claude Code


def parse_claude_get(text):
    """The fields of `claude mcp get NAME` output that a registration sets."""
    current, in_env = {"env": {}}, False
    for line in text.splitlines():
        stripped = line.strip()
        if in_env:
            if line.startswith("    ") and "=" in stripped:
                key, _, value = stripped.partition("=")
                current["env"][key] = value
                continue
            in_env = False
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        field = {"Scope": "scope", "Type": "type", "Command": "command", "Args": "args", "URL": "url"}.get(key)
        if field:
            current[field] = value.strip()
        elif key == "Environment":
            in_env = True
    return current


def claude(module, params):
    cli, name = params["claude_command"], params["name"]
    rc, out, err = module.run_command([*cli, "mcp", "get", name])
    if rc == 0:
        current = parse_claude_get(out)
    elif "No MCP server named" in out + err:
        current = None
    else:
        module.fail_json(msg=f"claude mcp get {name} failed: {(err or out).strip()}")
    if current is not None and not current.get("scope", "").startswith("User"):
        if params["state"] == "absent":
            module.warn(f"{name} is registered in Claude's {current.get('scope')}, which this play does not manage")
            module.exit_json(changed=False)
        module.fail_json(msg=f"{name} is registered in Claude's {current.get('scope')}, which hides the user registration; remove it there first")
    shown = None if current is None else {key: current.get(key) for key in ("type", "command", "args", "env") if key in current}

    if params["state"] == "absent":
        if current is None:
            module.exit_json(changed=False)
        if not module.check_mode:
            run(module, [*cli, "mcp", "remove", name, "-s", "user"])
        module.exit_json(changed=True, diff=diff(name, shown, None))

    desired = {"type": "stdio", "command": params["command"], "args": params["args"], "env": params["env"]}
    wanted = {**desired, "args": " ".join(params["args"])}
    if shown == wanted:
        module.exit_json(changed=False)
    if not module.check_mode:
        if current is not None:
            run(module, [*cli, "mcp", "remove", name, "-s", "user"])
        run(module, [*cli, "mcp", "add-json", "-s", "user", name, json.dumps({**desired, **params["extra"]})])
    module.exit_json(changed=True, diff=diff(name, shown, wanted))


def run(module, argv):
    rc, out, err = module.run_command(argv)
    if rc != 0:
        module.fail_json(msg=f"{' '.join(argv[:4])} failed: {(err or out).strip()}")


# Codex

HEADER = re.compile(r"^\s*\[\[?[^\]=]*\]\]?\s*(#.*)?$")
SERVER_TABLE = re.compile(r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|([A-Za-z0-9_-]+))\s*(?:\..*)?\]\s*(#.*)?$""")
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def without_tables(text, name):
    """text with every [mcp_servers.NAME] and [mcp_servers.NAME.*] table removed."""
    kept, skipping = [], False
    for line in text.splitlines(keepends=True):
        if HEADER.match(line):
            match = SERVER_TABLE.match(line)
            skipping = bool(match) and next(group for group in match.groups()[:3] if group is not None) == name
        if not skipping:
            kept.append(line)
    return "".join(kept)


def toml_key(key):
    return key if BARE_KEY.match(key) else json.dumps(key)


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_key(key)} = {toml_value(item)}" for key, item in value.items()) + " }" if value else "{}"
    raise TypeError(f"cannot write {value!r} as TOML")


def render_table(name, definition):
    lines = [f"[mcp_servers.{toml_key(name)}]"]
    lines += [f"{toml_key(key)} = {toml_value(value)}" for key, value in definition.items()]
    return "\n".join(lines) + "\n"


def others(document, name):
    """document without mcp_servers.NAME, to check nothing else changed."""
    rest = dict(document)
    servers = {key: value for key, value in rest.get("mcp_servers", {}).items() if key != name}
    rest.pop("mcp_servers", None)
    if servers:
        rest["mcp_servers"] = servers
    return rest


def codex(module, params):
    if tomllib is None:
        module.fail_json(msg="editing Codex config.toml needs Python 3.11 or later for tomllib")
    path, name = params["codex_config"], params["name"]
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        text = ""
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        module.fail_json(msg=f"{path} is not valid TOML: {error}")
    current = document.get("mcp_servers", {}).get(name)

    if params["state"] == "absent":
        desired = None
    else:
        desired = {"command": params["command"], "args": params["args"]}
        if params["env"]:
            desired["env"] = params["env"]
        desired.update(params["extra"])
    if current == desired:
        module.exit_json(changed=False)

    stripped = without_tables(text, name)
    try:
        remaining = tomllib.loads(stripped)
    except tomllib.TOMLDecodeError as error:
        module.fail_json(msg=f"removing [mcp_servers.{name}] from {path} would break it: {error}")
    if name in remaining.get("mcp_servers", {}) or others(remaining, name) != others(document, name):
        module.fail_json(msg=f"{path} defines mcp_servers.{name} outside its own table; edit it by hand")
    if desired is not None:
        stripped = stripped.rstrip("\n") + ("\n\n" if stripped.strip() else "") + render_table(name, desired)
        result = tomllib.loads(stripped)
        if result["mcp_servers"][name] != desired or others(result, name) != others(document, name):
            module.fail_json(msg=f"could not write mcp_servers.{name} to {path} without changing anything else")
    if not module.check_mode:
        write_atomically(path, stripped)
    module.exit_json(changed=True, diff=diff(name, current, desired))


def write_atomically(path, text):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    try:
        mode = os.stat(path).st_mode & 0o7777
    except FileNotFoundError:
        mode = 0o600
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=".config.toml.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise


def main():
    module = AnsibleModule(
        argument_spec={
            "provider": {"type": "str", "required": True, "choices": ["claude", "codex"]},
            "name": {"type": "str", "required": True},
            "state": {"type": "str", "default": "present", "choices": ["present", "absent"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str", "default": []},
            "env": {"type": "dict", "default": {}, "no_log": True},
            "extra": {"type": "dict", "default": {}},
            "claude_command": {"type": "list", "elements": "str", "default": ["claude"]},
            "codex_config": {"type": "path", "default": "~/.codex/config.toml"},
        },
        required_if=[("state", "present", ["command"])],
        supports_check_mode=True,
    )
    (claude if module.params["provider"] == "claude" else codex)(module, module.params)


if __name__ == "__main__":
    main()
