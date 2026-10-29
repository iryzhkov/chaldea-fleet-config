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
    ({"tag_name": "v00.1.6", "prerelease": False, "draft": False}, 200, "0.1.5", "unavailable"),
    ({"tag_name": "v0.1.6", "prerelease": False, "draft": False}, 200, "00.1.5", "unsupported_installed_version"),
    ({"tag_name": "v0.1.6\n", "prerelease": False, "draft": False}, 200, "0.1.5", "unavailable"),
    ({"tag_name": "v0.1.6", "prerelease": False, "draft": False}, 200, "0.1.5\n", "unsupported_installed_version"),
    ({"tag_name": "v" + "9" * 80 + ".1.6", "prerelease": False, "draft": False}, 200, "0.1.5", "unavailable"),
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
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    journal_record = tmp_path / "journal.json"
    logger = fake_bin / "logger"
    logger.write_text('#!/usr/bin/env python3\nimport json, os, pathlib, sys\n'
                      'assert sys.argv[1:4] == ["--tag", "chaldea-t3-release", "--"]\n'
                      'pathlib.Path(os.environ["T3_TEST_JOURNAL"]).write_text(sys.argv[4])\n')
    logger.chmod(0o755)
    play = tmp_path / "discovery.yml"
    discovery = next(task for task in yaml.safe_load(
        (ROOT / "roles/t3/tasks/main.yml").read_text()
    ) if task.get("ansible.builtin.include_tasks") == "update-check.yml")
    discovery["ansible.builtin.include_tasks"] = str(ROOT / "roles/t3/tasks/update-check.yml")
    play.write_text(yaml.safe_dump([{
        "hosts": "localhost", "gather_facts": False,
        "vars": {
            "t3_active_version": installed,
            "t3_version": "0.1.5",
            "t3_update_check_enabled": True,
            "t3_release_metadata_url": f"http://127.0.0.1:{server.server_port}/releases/latest",
        },
        "tasks": [discovery],
    }], sort_keys=False))
    env = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible"),
               ANSIBLE_NOCOLOR="1", PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
               T3_TEST_JOURNAL=str(journal_record))
    assert Path(env["HOME"]) == home
    try:
        command = ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)]
        result = subprocess.run(command + ["--check"], cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert requests == []
        assert not journal_record.exists()
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert requests == ["/releases/latest"]
        record = json.loads(journal_record.read_text())
        assert record["status"] == expected
        assert record["installed"] == installed
        assert record["pinned"] == "0.1.5"
        assert record["component"] == "t3"
        assert "changed=0" in result.stdout
        assert not (home / ".t3").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
