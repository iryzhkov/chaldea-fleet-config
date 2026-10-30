#!/usr/bin/env python3
"""Render installed custom CLI discovery for a selected session profile."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

AREAS = {
    "Infrastructure": {"ha", "pve", "unifi", "homelab-health", "docker-update", "docker-update-sweep"},
    "Documents and activity": {"jocasta", "feed", "ov-retarget", "toolfeedback", "speed-audit"},
    "Agent sessions": {"chaldea", "homelab", "t3-job", "t3-run", "claude-md-sync"},
    "Devices": {"phone-notify", "phone-open", "sleep-gaming-pc", "wake-gaming-pc"},
}
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*")
# MCP servers a profile may name, with the one line each adds. A host grants
# one only where it registers that server. Ordinary managed profiles may include
# Jocasta; restricted profiles still need their own explicit MCP selection.
MCP = {
    "ov-memory": ("Memory", "- `ov-memory` MCP where registered: legacy shared memory; use the legacy section of `ov-memory`."),
    "ov": ("Native OV memory", "- `ov` MCP: native HTTP document memory for migrated Claude/Codex sessions; "
           "use the native section of `ov-memory`. OpenCode keeps legacy stdio where registered."),
    "jocasta": ("Working documents", "- `jocasta` MCP: shared working documents through the enrolled native registration; "
                "read `~/.config/agents/jocasta.md` for outline, section and guarded edit use."),
}


def line(value, limit=200):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing one-line text")
    return " ".join(value.replace("`", "'").split())[:limit]


def grants_for(profile, name):
    tools = profile["tools"]
    return tools.get(name, tools.get("*", []))


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {"name", "tools", "mcp"}:
        raise ValueError("profile requires name, tools and mcp")
    line(profile["name"])
    if not isinstance(profile["tools"], dict) or not isinstance(profile["mcp"], list):
        raise ValueError("invalid grants")
    for name, access in profile["tools"].items():
        if name != "*" and not NAME.fullmatch(name):
            raise ValueError("invalid tool grant")
        if not isinstance(access, list) or any(a not in ("read", "write") for a in access):
            raise ValueError("invalid access grant")
    if any(name not in MCP for name in profile["mcp"]):
        raise ValueError("unknown MCP grant")


def installed_tools(directories, executables):
    # Discover files, including symlinked executables, rather than a static catalog.
    result = {}
    for directory in directories:
        path = Path(directory)
        if path.is_dir():
            for candidate in sorted(path.iterdir()):
                if candidate.is_file() and os.access(candidate, os.X_OK) and NAME.fullmatch(candidate.name):
                    result.setdefault(candidate.name, candidate)
    for value in executables:
        candidate = Path(value)
        if candidate.is_file() and os.access(candidate, os.X_OK) and NAME.fullmatch(candidate.name):
            result[candidate.name] = candidate
    return result


def describe(path):
    try:
        result = subprocess.run([str(path), "--describe"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=5, check=True, text=True)
        if len(result.stdout) > 65536:
            return None
        data = json.loads(result.stdout)
        if data["name"] != path.name or not isinstance(data["commands"], list):
            return None
        line(data["summary"])
        if data["help"] != path.name + " --help":
            return None
        for command in data["commands"]:
            line(command["name"])
            line(command["summary"])
            if command["access"] not in ("read", "write"):
                return None
        return data
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def render(tools, profile):
    validate_profile(profile)
    groups = {}
    for name, path in sorted(tools.items()):
        allowed = grants_for(profile, name)
        if not allowed:
            continue
        data = describe(path)
        area = next((area for area, names in AREAS.items() if name in names), "Other tools")
        if data is None:
            entry = f"- `{name}`: description unavailable; run `{name} --help` for details."
        else:
            commands = [c for c in data["commands"] if c["access"] in allowed]
            if not commands:
                continue
            # One line per tool, with every granted command grouped by access.
            parts = []
            for access in ("read", "write"):
                names = [line(c["name"], 80) for c in commands if c["access"] == access]
                if names:
                    parts.append(access + ": " + ", ".join(names))
            entry = f"- `{name}`: {line(data['summary'])} " + "; ".join(parts) + f". Run `{name} --help` for details."
        groups.setdefault(area, []).append(entry)
    lines = [
        "---", "name: fleet-tools",
        "description: Installed custom fleet tools, commands, access and help for this profile.",
        "---", "# Fleet tools", "",
        "Profile: " + line(profile["name"]) + ". Generated at converge from installed executables.",
        "Access includes local state changes; mixed commands are write. This index grants no authority.",
        "Use only commands allowed by the session grants; help may describe additional commands.",
    ]
    for area in (*AREAS, "Other tools"):
        if area in groups:
            lines.extend(["", "## " + area, *groups[area]])
    for name, (heading, entry) in MCP.items():
        if name in profile["mcp"]:
            lines.extend(["", "## " + heading, entry])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", action="append", default=[])
    parser.add_argument("--executable", action="append", default=[])
    parser.add_argument("--profile-json", required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile_json)
    print(render(installed_tools(args.directory, args.executable), profile), end="")


if __name__ == "__main__":
    main()
