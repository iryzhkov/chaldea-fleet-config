#!/usr/bin/python
"""Register one MCP server with Claude Code, Codex or OpenCode, idempotently."""

DOCUMENTATION = r"""
module: mcp_registration
short_description: Register one MCP server with Claude Code, Codex or OpenCode
description:
  - For Claude Code, reads the user-scope registration with C(claude mcp get)
    and replaces it through C(claude mcp remove) and C(claude mcp add-json -s user)
    when it differs. ~/.claude.json is never edited directly.
  - For Codex, rewrites only the [mcp_servers.NAME] tables of config.toml and
    refuses when the result would change anything else in the file.
  - For OpenCode, updates only mcp.NAME in opencode.json, preserving other settings.
  - Environment values never appear in the diff or the result.
  - transport=remote registers an HTTP server with the client's native OAuth,
    from a URL and the provider's public OAuth options in extra (client ID,
    scopes, callback). It never writes command, args, env, headers, header
    helpers, bearer tokens or client secrets, and refuses extra keys outside
    that public allowlist. Native login stays with the user.
  - auth_mode=managed_helper is a separate closed Jocasta capability for Claude
    and Codex. It emits only the fixed public helper command for helper_host,
    requires empty extra and never accepts arbitrary helper or secret fields.
  - claude mcp get does not show the OAuth options, so for a remote server the
    module reads the one user registration from claude_config to compare it.
    Only allowlisted public fields keep their values; any other field counts as
    drift and is shown as <redacted>. Claude's credential store is never read.
options:
  provider: {description: claude, codex or opencode, required: true, type: str}
  name: {description: Server name, required: true, type: str}
  state: {description: present or absent, default: present, type: str}
  transport: {description: stdio or remote, default: stdio, type: str}
  command: {description: Executable of a stdio server, type: str}
  args: {description: Its arguments, type: list, elements: str}
  env: {description: Environment the server gets, type: dict}
  url: {description: HTTPS URL of a remote server, type: str}
  auth_mode: {description: oauth or closed managed_helper mode, default: oauth, type: str}
  helper_host: {description: Explicit approved host in managed_helper mode, type: str}
  extra: {description: Further provider-specific keys, type: dict}
  claude_command: {description: The claude CLI as an argument list, type: list, elements: str}
  claude_config: {description: Claude's user config, read only for a remote server, type: path}
  codex_config: {description: Path of Codex config.toml, type: path}
  opencode_config: {description: Path of OpenCode JSON config, type: path}
"""

import json
import os
import re
import stat
import tempfile
from urllib.parse import urlsplit

try:
    import tomllib
except ImportError:  # Python before 3.11
    tomllib = None

from ansible.module_utils.basic import AnsibleModule


def redacted(definition, previous=None):
    """definition with each env value replaced by whether it differs from previous."""
    if not isinstance(definition, dict):
        return definition
    shown = dict(definition)
    for field in ("env", "environment", "headers", "oauth"):
        if isinstance(shown.get(field), dict):
            old = previous.get(field, {}) if isinstance(previous, dict) else {}
            old = old if isinstance(old, dict) else {}
            shown[field] = {key: "<redacted>" if previous is None or old.get(key) == value
                            else "<redacted, changed>" for key, value in shown[field].items()}
    return shown


def diff(name, before, after, view=redacted):
    def text(definition):
        return "" if definition is None else json.dumps(definition, indent=2, sort_keys=True) + "\n"

    return {"before_header": name, "after_header": name, "before": text(view(before)), "after": text(view(after, before or {}))}


# Remote servers. Each provider's own schema for an HTTP server with native
# OAuth: the keys the module sets, then the public keys extra may add.
REMOTE_BASE = {"claude": {"type", "url"}, "codex": {"url"}, "opencode": {"type", "url", "enabled"}}
REMOTE_EXTRA = {"claude": {"oauth"}, "codex": {"scopes", "oauth"}, "opencode": {"oauth"}}
REMOTE_OAUTH = {
    "claude": {"clientId", "callbackPort", "scopes"},
    "codex": {"client_id", "callback_port", "callback_url"},
    "opencode": {"clientId", "scope", "callbackPort", "redirectUri"},
}
PORTS = {"callbackPort", "callback_port"}
HELPER_FIELDS = {"claude": "headersHelper", "codex": "http_headers_helper"}
HELPER = "/usr/local/libexec/webmcp-interactive-headers jocasta "
MANAGED_HOSTS = {"laptop", "agent-a", "agent-b", "omarchy-pc"}


def managed_helper(value):
    return isinstance(value, str) and value in {HELPER + host for host in MANAGED_HOSTS}


class Hidden:
    """A value outside the public allowlist: compared by presence, never kept or shown."""

    def __eq__(self, other):
        return isinstance(other, Hidden)

    def __hash__(self):
        return 0


HIDDEN = Hidden()


def public_text(value):
    return isinstance(value, str) and value != "" and value.isprintable() and value == value.strip()


def public_url(value):
    """An absolute HTTPS URL that carries no credentials, query or fragment."""
    if not public_text(value) or " " in value:
        return False
    try:
        parts = urlsplit(value)
        return (parts.scheme == "https" and bool(parts.hostname) and parts.username is None
                and parts.password is None and not parts.query and not parts.fragment and parts.port != 0)
    except ValueError:
        return False


def public_value(key, value):
    if key in PORTS:
        return type(value) is int and 0 < value < 65536
    if key == "url":
        return public_url(value)
    if key == "enabled":
        return type(value) is bool
    if isinstance(value, list):
        return bool(value) and all(public_text(item) for item in value)
    return public_text(value)


def public_projection(provider, entry):
    """entry with every value outside the provider's public allowlist replaced by HIDDEN."""
    if not isinstance(entry, dict):
        return HIDDEN
    keys = REMOTE_BASE[provider] | REMOTE_EXTRA[provider]
    shown = {}
    for key, value in entry.items():
        if key == "oauth" and isinstance(value, dict):
            shown[key] = {field: item if field in REMOTE_OAUTH[provider] and public_value(field, item) else HIDDEN
                          for field, item in value.items()}
        elif key == HELPER_FIELDS.get(provider) and managed_helper(value):
            shown[key] = value
        elif key in keys and key != "oauth" and public_value(key, value):
            shown[key] = value
        else:
            shown[key] = HIDDEN
    return shown


def remote_view(definition, previous=None):
    """A projection for a diff: type, URL, scopes and enabled shown, the rest <redacted>."""
    if definition is None or isinstance(definition, Hidden):
        return definition if definition is None else "<redacted>"
    old = previous if isinstance(previous, dict) else {}

    def marker(same):
        return "<redacted>" if previous is None or same else "<redacted, changed>"

    shown = {}
    for key, value in definition.items():
        if isinstance(value, dict):
            before = old.get(key) if isinstance(old.get(key), dict) else {}
            shown[key] = {field: marker(before.get(field) == item) for field, item in value.items()}
        elif isinstance(value, Hidden):
            shown[key] = marker(old.get(key) == value)
        else:
            shown[key] = value
    return shown


def remote_definition(module, provider, params):
    """The provider's native public definition of a remote server, or a refusal."""
    extra = params["extra"]
    if params.get("auth_mode", "oauth") == "managed_helper":
        host = params.get("helper_host")
        if (provider not in HELPER_FIELDS or host not in MANAGED_HOSTS or extra
                or params["name"] != "jocasta" or params["url"] != "https://jocasta.mcp.ryzhkov.dev/mcp"):
            module.fail_json(msg="managed_helper requires the fixed Jocasta resource, approved host and native Claude/Codex provider, without extra options")
        definition = {"url": params["url"], HELPER_FIELDS[provider]: HELPER + host}
        return {"type": "http", **definition} if provider == "claude" else definition
    if params.get("helper_host") is not None:
        module.fail_json(msg="helper_host belongs only to managed_helper auth mode")
    unknown = sorted(set(extra) - REMOTE_EXTRA[provider])
    oauth = extra.get("oauth", {})
    if not isinstance(oauth, dict):
        unknown.append("oauth")
    else:
        unknown += sorted("oauth." + field for field in set(oauth) - REMOTE_OAUTH[provider])
    if unknown:
        module.fail_json(msg=f"a remote {provider} server takes only public OAuth options; refusing {', '.join(unknown)}")
    if public_projection(provider, extra) != extra or (isinstance(oauth, dict) and not oauth):
        module.fail_json(msg=f"the public OAuth options for {params['name']} must be nonempty text, text lists or ports")
    if provider == "claude":
        return {"type": "http", "url": params["url"], **extra}
    if provider == "codex":
        return {"url": params["url"], **extra}
    return {"type": "remote", "url": params["url"], **extra, "enabled": True}


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
        if line.startswith("   "):
            continue  # A header or other nested line, never a top-level field.
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
    remote = params["transport"] == "remote"
    rc, out, err = module.run_command([*cli, "mcp", "get", name])
    if rc == 0:
        current = parse_claude_get(out)
    elif "No MCP server named" in out + err:
        current = None
    elif remote:
        # get prints a remote server's header values; never echo its output.
        module.fail_json(msg=f"claude mcp get {name} failed with status {rc}")
    else:
        module.fail_json(msg=f"claude mcp get {name} failed: {(err or out).strip()}")
    if current is not None and not current.get("scope", "").startswith("User"):
        if params["state"] == "absent":
            module.warn(f"{name} is registered in Claude's {current.get('scope')}, which this play does not manage")
            module.exit_json(changed=False)
        module.fail_json(msg=f"{name} is registered in Claude's {current.get('scope')}, which hides the user registration; remove it there first")
    if remote:
        claude_remote(module, params, current)
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


def claude_user_registration(module, path, name):
    """The public projection of mcpServers.NAME in Claude's user config, or None.

    The file holds unrelated private state, so nothing else from it is kept,
    returned or quoted in a message.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        module.fail_json(msg="Claude's user config cannot be inspected; reconcile it before registering a remote server")
    if not stat.S_ISREG(info.st_mode):
        module.fail_json(msg="Claude's user config is not a regular file (a symlink?); reconcile it before registering a remote server")
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(handle, encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, ValueError):
        document = None
    servers = document.get("mcpServers", {}) if isinstance(document, dict) else None
    if not isinstance(servers, dict) or not isinstance(servers.get(name, {}), dict):
        module.fail_json(msg="Claude's user config must be a readable JSON object whose mcpServers entries are objects")
    entry = servers.get(name)
    return None if entry is None else public_projection("claude", entry)


def claude_remote(module, params, current):
    """Reconcile a user-scope remote registration through the claude CLI only."""
    cli, name = params["claude_command"], params["name"]
    stored = claude_user_registration(module, params["claude_config"], name)
    # Both views must name the same registration; get shows type and URL only.
    if (current is None) != (stored is None) or current is not None and any(
            key in current and key in stored and not isinstance(stored[key], Hidden) and current[key] != stored[key]
            for key in ("type", "url")):
        module.fail_json(msg=f"claude mcp get and {params['claude_config']} disagree about {name}; reconcile it by hand")
    if params["state"] == "absent":
        if stored is None:
            module.exit_json(changed=False)
        if not module.check_mode:
            run_remote(module, [*cli, "mcp", "remove", name, "-s", "user"])
        module.exit_json(changed=True, diff=diff(name, stored, None, remote_view))
    desired = remote_definition(module, "claude", params)
    if stored == desired:
        module.exit_json(changed=False)
    if not module.check_mode:
        if stored is not None:
            run_remote(module, [*cli, "mcp", "remove", name, "-s", "user"])
        run_remote(module, [*cli, "mcp", "add-json", "-s", "user", name, json.dumps(desired)])
    module.exit_json(changed=True, diff=diff(name, stored, desired, remote_view))


def run_remote(module, argv):
    rc, _out, _err = module.run_command(argv)
    if rc != 0:
        module.fail_json(msg=f"remote MCP registration command failed with status {rc}")


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
    remote = params["transport"] == "remote"

    if params["state"] == "absent":
        desired = None
    elif remote:
        desired = remote_definition(module, "codex", params)
    else:
        desired = {"command": params["command"], "args": params["args"]}
        if params["env"]:
            desired["env"] = params["env"]
        desired.update(params["extra"])
    if remote:
        # Compare and show only public fields; other values never leave this function.
        current = None if current is None else public_projection("codex", current)
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
    module.exit_json(changed=True, diff=diff(name, current, desired, remote_view if remote else redacted))


# OpenCode. Its environment/command schema differs from Claude and Codex.


def opencode(module, params):
    path, name = params["opencode_config"], params["name"]
    if os.path.islink(path) or os.path.exists(os.path.splitext(path)[0] + ".jsonc"):
        module.fail_json(msg="OpenCode config is a symlink or has a JSONC peer; reconcile the owning config first")
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError:
        document = {}
    except (ValueError, OSError):
        module.fail_json(msg="OpenCode config must be a readable JSON object")
    if not isinstance(document, dict) or not isinstance(document.get("mcp", {}), dict):
        module.fail_json(msg="OpenCode config and mcp must be JSON objects")
    current = document.get("mcp", {}).get(name)
    remote = params["transport"] == "remote"
    if params["state"] == "absent":
        desired = None
    elif remote:
        desired = remote_definition(module, "opencode", params)
    else:
        desired = {
            **params["extra"], "type": "local", "command": [params["command"], *params["args"]],
            "environment": params["env"], "enabled": True,
        }
    if remote and current is not None:
        current = public_projection("opencode", current)
    if current == desired:
        module.exit_json(changed=False)
    servers = dict(document.get("mcp", {}))
    if desired is None:
        servers.pop(name, None)
    else:
        servers[name] = desired
    updated = {**document, "mcp": servers}
    if not module.check_mode:
        write_atomically(path, json.dumps(updated, indent=2, ensure_ascii=False) + "\n")
    module.exit_json(changed=True, diff=diff(name, current, desired, remote_view if remote else redacted))


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
            "provider": {"type": "str", "required": True, "choices": ["claude", "codex", "opencode"]},
            "name": {"type": "str", "required": True},
            "state": {"type": "str", "default": "present", "choices": ["present", "absent"]},
            "transport": {"type": "str", "default": "stdio", "choices": ["stdio", "remote"]},
            "command": {"type": "str"},
            "args": {"type": "list", "elements": "str", "default": []},
            "env": {"type": "dict", "default": {}, "no_log": True},
            "url": {"type": "str"},
            "auth_mode": {"type": "str", "default": "oauth", "choices": ["oauth", "managed_helper"]},
            "helper_host": {"type": "str"},
            "extra": {"type": "dict", "default": {}},
            "claude_command": {"type": "list", "elements": "str", "default": ["claude"]},
            "claude_config": {"type": "path", "default": "~/.claude.json"},
            "codex_config": {"type": "path", "default": "~/.codex/config.toml"},
            "opencode_config": {"type": "path", "default": "~/.config/opencode/opencode.json"},
        },
        supports_check_mode=True,
    )
    check_transport(module, module.params)
    {"claude": claude, "codex": codex, "opencode": opencode}[module.params["provider"]](module, module.params)


def check_transport(module, params):
    """A stdio server needs a command; a remote one a public HTTPS URL and no stdio fields."""
    if params["transport"] == "stdio":
        if params.get("auth_mode", "oauth") != "oauth" or params.get("helper_host") is not None:
            module.fail_json(msg="managed helper authentication requires remote transport")
        if params["url"] is not None:
            module.fail_json(msg="url belongs to a remote server; set transport: remote")
        if params["state"] == "present" and not params["command"]:
            module.fail_json(msg="state is present but all of the following are missing: command")
        return
    if params["command"] is not None or params["args"] or params["env"]:
        module.fail_json(msg="a remote server takes a url, not command, args or env")
    if params["state"] == "present" and not public_url(params["url"]):
        module.fail_json(msg="a remote server needs an https URL without credentials, query or fragment")


if __name__ == "__main__":
    main()
