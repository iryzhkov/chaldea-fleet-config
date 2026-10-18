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


class Client:
    def __init__(self, binary, socket):
        self.process = subprocess.Popen(
            [binary, "mcp", "--socket", socket, "--profile", "full", "--reply-style", "json"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
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


def check(binary, socket, root, languages):
    if not languages or len(set(languages)) != len(languages) or set(languages) - SERVERS.keys():
        raise ValueError("expected a unique nonempty subset of the strict nine languages")
    client = Client(binary, socket)
    try:
        client.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "fleet-health", "version": "1"}})
        client.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        client.process.stdin.flush()
        checked = []
        for language in languages:
            arguments = {"root": str(Path(root) / language)}
            opened = client.call("workspace_open", arguments)
            if opened.get("outcome") in ("failed", "unavailable", "conflict"):
                raise ValueError("health workspace could not open: " + opened.get("summary", ""))
            inspection = client.call("workspace_inspect", arguments)
            provider = (inspection.get("data") or {}).get("semantic_provider") or {}
            if (inspection.get("outcome") in ("failed", "unavailable")
                    or provider.get("state") != "healthy"):
                raise ValueError("workspace_inspect health failed: " + inspection.get("summary", ""))
            status = client.call("language_server_status", dict(arguments, languages=[FILETYPES.get(language, language)]))
            checked.append(presence(language, status))
        return {"expected_languages": languages, "servers": checked}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser()
    for name in ("binary", "socket", "root", "languages"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.binary, args.socket, args.root, json.loads(args.languages))))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
