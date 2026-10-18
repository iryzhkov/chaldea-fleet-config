#!/usr/bin/env python3
"""Read-only MCP service health and server-presence checks after fleet activation."""
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import time

FILETYPES = {"bash": "sh"}
SERVERS = {"go": "gopls", "rust": "rust_analyzer", "python": "pyright",
           "typescript": "ts_ls", "javascript": "ts_ls", "java": "jdtls",
           "cpp": "clangd", "c": "clangd", "bash": "bashls"}
EXECUTABLES = dict(SERVERS, rust="rust-analyzer", python="pyright-langserver",
                   typescript="typescript-language-server", javascript="typescript-language-server",
                   bash="bash-language-server")


class Client:
    def __init__(self, binary, socket):
        self.process = subprocess.Popen(
            [binary, "mcp", "--socket", socket, "--profile", "full", "--reply-style", "json"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.sequence = 0
        self.pending = b""

    def rpc(self, method, params):
        self.sequence += 1
        self.process.stdin.write((json.dumps({"jsonrpc": "2.0", "id": self.sequence,
                                             "method": method, "params": params}) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 110
        while time.monotonic() < deadline:
            if b"\n" not in self.pending:
                readable, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
                if not readable:
                    break
                data = os.read(self.process.stdout.fileno(), 65536)
                if not data:
                    raise ValueError("Huyang adapter closed before answering")
                self.pending += data
                if len(self.pending) > 16 * 1024 * 1024:
                    raise ValueError("Huyang response exceeds health-client limit")
                continue
            line, self.pending = self.pending.split(b"\n", 1)
            response = json.loads(line)
            if response.get("id") == self.sequence:
                if "error" in response:
                    raise ValueError("Huyang RPC failed: " + str(response["error"]))
                return response["result"]
        raise ValueError("Huyang health request timed out")

    def call(self, name, arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        envelope = result.get("structuredContent")
        if envelope is None:
            for item in result.get("content", []):
                if item.get("type") == "text":
                    envelope = json.loads(item["text"])
                    break
        if not isinstance(envelope, dict):
            raise ValueError("Huyang returned no structured health envelope")
        return envelope

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def presence(language, reply):
    expected_type = FILETYPES.get(language, language)
    rows = ((reply.get("data") or {}).get("language_servers") or {}).get("languages", [])
    row = next((item for item in rows if item.get("filetype") == expected_type), None)
    if row is None:
        raise ValueError("missing required server status for " + language)
    server = SERVERS[language]
    # A configured server may still be starting or delayed by capacity. Presence,
    # rather than attachment latency or project diagnostics, is this converge gate.
    configured = row.get("configured", [])
    description = row.get("lsp", "")
    if (row.get("attach") == "unconfigured"
            or not (server in description or server in configured
                    or server in row.get("enabled_from_system", ""))):
        raise ValueError("missing required server " + server + " for " + language)
    return {"language": language, "server": server, "attach": row.get("attach"),
            "parser": row.get("treesitter_parser_installed", row.get("treesitter_parser"))}


def is_capacity(reply):
    message = str(reply.get("code", "")) + " " + str(reply.get("summary", ""))
    return any(term in message.lower() for term in
               ("provider capacity", "provider_capacity", "language_server_capacity", "capacity exhausted"))


def require_executables(toolchain_bin, languages):
    directory = Path(toolchain_bin)
    if not directory.is_absolute():
        raise ValueError("toolchain bin must be absolute")
    for language in languages:
        executable = directory / EXECUTABLES[language]
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("missing required server executable for " + language + ": " + str(executable))


def probe_language(client, arguments, language):
    for attempt in range(3):
        opened = client.call("workspace_open", arguments)
        if not is_capacity(opened):
            if opened.get("outcome") in ("failed", "unavailable", "conflict"):
                raise ValueError("health workspace could not open: " + opened.get("summary", ""))
            inspection = client.call("workspace_inspect", arguments)
            status = client.call("language_server_status", dict(
                arguments, languages=[FILETYPES.get(language, language)]))
            if not is_capacity(inspection) and not is_capacity(status):
                provider = (inspection.get("data") or {}).get("semantic_provider") or {}
                if inspection.get("outcome") in ("failed", "unavailable"):
                    raise ValueError("workspace_inspect health failed: " + inspection.get("summary", ""))
                if provider.get("state") == "healthy":
                    return presence(language, status)
                # The status call may acquire a slot after inspect was refused.
                live = (status.get("data") or {}).get("provider") or {}
                if live.get("state") != "healthy":
                    raise ValueError("workspace_inspect provider is unhealthy")
        if attempt < 2:
            time.sleep(0.25)
    # Installation already proved executable/config/parser presence. Capacity is
    # pending runtime evidence, never evidence that a required server is absent.
    return {"language": language, "server": SERVERS[language], "attach": "deferred_capacity"}


def check(binary, socket, root, languages, toolchain_bin):
    if not languages or len(set(languages)) != len(languages) or set(languages) - SERVERS.keys():
        raise ValueError("expected a unique nonempty subset of the strict nine languages")
    require_executables(toolchain_bin, languages)
    client = Client(binary, socket)
    try:
        client.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "fleet-health", "version": "1"}})
        client.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        client.process.stdin.flush()
        checked = []
        for language in languages:
            arguments = {"root": str(Path(root) / language)}
            checked.append(probe_language(client, arguments, language))
        deferred = [entry["language"] for entry in checked if entry["attach"] == "deferred_capacity"]
        return {"expected_languages": languages, "servers": checked, "complete": not deferred,
                "deferred_languages": deferred,
                "warnings": ["Provider capacity delayed health; the next converge retries without restart."] if deferred else []}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser()
    for name in ("binary", "socket", "root", "languages", "toolchain-bin"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.binary, args.socket, args.root, json.loads(args.languages), args.toolchain_bin)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
