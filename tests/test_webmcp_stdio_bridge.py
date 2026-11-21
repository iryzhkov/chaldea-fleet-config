"""The closed Antigravity stdio bridge, with a fake helper and fake HTTPS.

Nothing here runs the real helper, reads a credential or contacts a server.
"""
import importlib.util
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "roles/webmcp_interactive/files/webmcp-stdio-bridge"
TOKEN = "Bearer SECRET-sentinel-7d31"


def load_bridge():
    loader = SourceFileLoader("webmcp_stdio_bridge", str(SOURCE))
    spec = importlib.util.spec_from_loader("webmcp_stdio_bridge", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


bridge = load_bridge()


class Helper:
    """A fake subprocess.run for the fixed helper."""

    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        code, out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        return subprocess.CompletedProcess(argv, code, stdout=out.encode())


def header(value=TOKEN):
    return 0, json.dumps({"Authorization": value})


class Response(io.BytesIO):
    def __init__(self, status=200, kind="application/json", body=b"", headers=None):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": kind, **(headers or {})}


class Opener:
    """Records requests; answers from a script of responses or HTTP errors.

    A dict script routes by JSON-RPC method (or DELETE), so messages that the
    bridge sends from worker threads get deterministic answers.
    """

    def __init__(self, script):
        self.script = {key: list(value) for key, value in script.items()} if isinstance(script, dict) else list(script)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        if isinstance(self.script, dict):
            key = request.get_method() if request.data is None else json.loads(request.data)["method"]
            answer = self.script[key].pop(0)
        else:
            answer = self.script.pop(0)
        if isinstance(answer, int):
            raise urllib.error.HTTPError(request.full_url, answer, "error", {}, io.BytesIO(b"denied body"))
        return answer


def make(script, outputs=(header(),), clock=None):
    times = iter(clock or [0.0] * 100)
    return bridge.Bridge("https://jocasta.mcp.ryzhkov.dev/mcp", "jocasta", "laptop", run=Helper(outputs),
                         opener=Opener(script), clock=lambda: next(times))


def serve(instance, *messages, capsys):
    bridge.serve(instance, io.StringIO("".join(json.dumps(m) + "\n" for m in messages)))
    out, err = capsys.readouterr()
    assert TOKEN not in out + err and "SECRET" not in out + err
    return [json.loads(line) for line in out.splitlines()], err


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}


def sse(*payloads):
    return "".join(f"event: message\nid: {i}\ndata: {json.dumps(p)}\n\n" for i, p in enumerate(payloads)).encode()


@pytest.mark.parametrize("argv", [[], ["jocasta"], ["jocasta", "normandy"], ["shizune", "agent-a"],
                                  ["ov", "agent-b"], ["holonet", "laptop"], ["jocasta", "laptop", "extra"],
                                  ["https://evil.example/mcp", "laptop"]])
def test_only_the_closed_tuples_start(argv, capsys):
    assert bridge.main(argv) == 2
    assert "usage" in capsys.readouterr().err


def test_session_protocol_sse_and_fixed_helper_invocation(capsys):
    init = Response(body=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}}).encode(),
                    headers={"Mcp-Session-Id": "session-1"})
    listed = Response(kind="text/event-stream", body=sse(
        {"jsonrpc": "2.0", "method": "notifications/progress"},
        {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "get"}]}}))
    instance = make({"initialize": [init], "notifications/initialized": [Response(status=202, kind="")],
                     "tools/list": [listed], "DELETE": [Response(status=200)]})
    replies, _ = serve(instance, INIT, INITIALIZED, LIST, capsys=capsys)
    assert replies[0]["id"] == 1 and replies[-1] == {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "get"}]}}
    assert len(replies) == 3
    requests = instance.opener.requests
    assert sorted(r.get_method() for r in requests) == ["DELETE", "POST", "POST", "POST"]
    assert requests[0].get_method() == "POST" and requests[-1].get_method() == "DELETE"
    assert all(r.full_url == "https://jocasta.mcp.ryzhkov.dev/mcp" for r in requests)
    assert requests[0].get_header("Mcp-session-id") is None
    assert all(r.get_header("Mcp-session-id") == "session-1" for r in requests[1:])
    assert all(r.get_header("Mcp-protocol-version") == "2025-06-18" for r in requests[1:])
    assert all(r.get_header("Authorization") == TOKEN for r in requests)
    # One helper call for the whole session within the TTL, with the fixed tuple and no environment.
    assert instance.run.calls == [([bridge.HELPER, "jocasta", "laptop"], instance.run.calls[0][1])]
    assert instance.run.calls[0][1]["env"] == {} and instance.run.calls[0][1]["stderr"] == subprocess.DEVNULL


def test_401_refreshes_the_header_once_then_fails_closed(capsys):
    ok = Response(body=json.dumps({"jsonrpc": "2.0", "id": 2, "result": {}}).encode())
    instance = make([401, ok], outputs=[header("Bearer old-SECRET"), header()])
    replies, _ = serve(instance, LIST, capsys=capsys)
    assert replies == [{"jsonrpc": "2.0", "id": 2, "result": {}}]
    assert [r.get_header("Authorization") for r in instance.opener.requests] == ["Bearer old-SECRET", TOKEN]
    instance = make([401, 401])
    replies, err = serve(instance, LIST, capsys=capsys)
    assert replies[0]["error"]["message"] == "upstream request failed (401)"
    assert "denied body" not in json.dumps(replies) + err


def test_header_cache_expires():
    # Clock reads: fetch time, then one check per later call, then the refetch time.
    instance = make([], outputs=[header("Bearer one"), header("Bearer two")], clock=[0.0, 0.0, 59.0, 60.0, 60.0])
    assert [instance.authorization() for _ in range(4)] == ["Bearer one"] * 3 + ["Bearer two"]
    assert len(instance.run.calls) == 2


@pytest.mark.parametrize("output", [(1, ""), (0, "not json"), (0, json.dumps({"Authorization": "Basic x"})),
                                    (0, json.dumps({"Authorization": TOKEN, "X-Extra": "y"})),
                                    (0, json.dumps({"Authorization": "Bearer a\r\nX-Injected: 1"})),
                                    (0, json.dumps([TOKEN]))])
def test_helper_failure_or_malformed_output_never_reaches_the_server(output, capsys):
    instance = make([], outputs=[output])
    replies, err = serve(instance, LIST, capsys=capsys)
    assert replies[0]["id"] == 2 and replies[0]["error"]["code"] == bridge.UPSTREAM_ERROR
    assert instance.opener.requests == []
    assert "Basic" not in err + json.dumps(replies)


def test_expired_session_and_unreadable_response(capsys):
    init = Response(body=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode(), headers={"Mcp-Session-Id": "s"})
    instance = make([init, 404, Response(status=200)])
    replies, _ = serve(instance, INIT, LIST, capsys=capsys)
    assert replies[-1]["error"]["code"] == bridge.SESSION_EXPIRED
    instance = make([Response(body=b"{broken")])
    replies, _ = serve(instance, LIST, capsys=capsys)
    assert replies[0]["error"]["message"] == "upstream response unreadable"


def test_default_opener_ignores_proxies_and_refuses_redirects(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:1")
    instance = bridge.Bridge("https://jocasta.mcp.ryzhkov.dev/mcp", "jocasta", "laptop")
    handlers = instance.opener.handlers
    # ProxyHandler({}) has no *_open methods, so no proxy handler is installed at all.
    assert not any(isinstance(h, urllib.request.ProxyHandler) and h.proxies for h in handlers)
    assert "urllib.request.ProxyHandler({})" in SOURCE.read_text()
    redirect = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
    assert isinstance(redirect, bridge.NoRedirect)
    assert redirect.redirect_request(None, None, 302, "Found", {}, "https://evil.example/") is None


def test_the_script_runs_isolated_and_is_executable():
    assert SOURCE.read_text().startswith("#!/usr/bin/python3 -I\n")
    assert SOURCE.stat().st_mode & 0o111
    result = subprocess.run([sys.executable, "-I", str(SOURCE), "jocasta", "evil"], capture_output=True, text=True)
    assert result.returncode == 2 and result.stdout == ""
