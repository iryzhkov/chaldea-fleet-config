"""Exercise unattended discovery against a local release API, without T3."""
import json
import os
from pathlib import Path
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("release,http_status,installed,expected", [
    ({"tag_name": "v0.1.6", "prerelease": False, "draft": False}, 200, "0.1.5", "update_available"),
    ({"tag_name": "v0.1.5", "prerelease": False, "draft": False}, 200, "0.1.5", "current"),
    ({"tag_name": "v0.1.4", "prerelease": False, "draft": False}, 200, "0.1.5", "installed_ahead"),
    ({"tag_name": "v0.1.6-preview.1", "prerelease": True, "draft": False}, 200, "0.1.5", "unavailable"),
    ({"tag_name": "v0.1.6", "prerelease": False, "draft": True}, 200, "0.1.5", "unavailable"),
    ({"message": "rate limited"}, 503, "0.1.5", "unavailable"),
    (["invalid metadata"], 200, "0.1.5", "unavailable"),
    ({"tag_name": "v0.1.6", "prerelease": False, "draft": False}, 200, "0.1.5-nightly.1", "unsupported_installed_version"),
])
def test_release_discovery_is_read_only(tmp_path, release, http_status, installed, expected):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(http_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(release).encode())

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    home = tmp_path / "home"
    home.mkdir()
    play = tmp_path / "discovery.yml"
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {
            "t3_active_version": installed,
            "t3_version": "0.1.5",
            "t3_update_check_enabled": True,
            "t3_release_metadata_url": f"http://127.0.0.1:{server.server_port}/releases/latest",
        },
        "tasks": [{
            "ansible.builtin.include_tasks": str(ROOT / "roles/t3/tasks/update-check.yml"),
            # Same production inclusion condition: check mode must never fetch.
            "when": "t3_update_check_enabled | bool and not ansible_check_mode",
        }],
    }], sort_keys=False))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"),
               ANSIBLE_NOCOLOR="1")
    assert Path(env["HOME"]) == home
    try:
        command = ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
        result = subprocess.run(command + ["--check"], cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert requests == []
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert requests == ["/releases/latest"]
        assert f'"status": "{expected}"' in result.stdout, result.stdout
        assert "changed=0" in result.stdout
        assert not (home / ".t3").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
