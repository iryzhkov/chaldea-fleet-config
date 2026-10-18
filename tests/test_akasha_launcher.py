"""Manual ship and the timer must share a lock and cursor store."""
import fcntl
import json
import os
from pathlib import Path
import subprocess

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


def test_manual_collector_uses_timer_lock_and_drops_shared_key(tmp_path):
    home = tmp_path / "home"
    state = home / ".local/state/chaldea/events"
    state.mkdir(parents=True)
    script = tmp_path / "collector.py"
    capture = tmp_path / "capture"
    script.write_text("import json,os,sys\n"
                      "print(json.dumps([sys.argv[1:], {k:v for k,v in os.environ.items() "
                      "if k.startswith(('AKASHA_','FEED_'))}]))\n")
    env = Environment(loader=FileSystemLoader(ROOT / "roles/akasha_collector/templates"),
                      undefined=StrictUndefined)
    launcher = tmp_path / "launcher"
    launcher.write_text(env.get_template("akasha-collector.j2").render(
        fleet_home=str(home), akasha_collector_url="https://akasha.ryzhkov.dev",
        akasha_collector_token_helper="/approved/helper",
        akasha_collector_node="/usr/bin/python3", akasha_collector_script=str(script)))
    process_env = {**os.environ, "FEED_TOKEN": "must-not-reach-collector",
                   "FEED_KEY_FILE": "/never/open", "FEED_CONFIG": "/never/source"}
    with (state / "collector.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(["sh", str(launcher), "--dry-run"], env=process_env, capture_output=True, text=True)
        assert result.returncode != 0 and result.stdout == ""
    result = subprocess.run(["sh", str(launcher), "--dry-run"], env=process_env, capture_output=True, text=True, check=True)
    args, configured = json.loads(result.stdout)
    assert args == ["--dry-run"]
    assert configured["AKASHA_STATE_FILE"] == str(state / "collector.db")
    assert configured["AKASHA_TOKEN_HELPER"] == "/approved/helper"
    assert not any(k.startswith("FEED_") for k in configured)
