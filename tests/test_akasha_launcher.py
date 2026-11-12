"""Manual ship and the timer must share a lock and cursor store."""
import fcntl
import hashlib
import io
import tarfile
import urllib.request

import yaml
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
    script.write_text("import json,os,sys\n"
                      "from pathlib import Path\n"
                      "config=json.loads((Path(os.environ['XDG_CONFIG_HOME'])/'chaldea/events.json').read_text())\n"
                      "print(json.dumps([sys.argv[1:], config, {k:v for k,v in os.environ.items() "
                      "if k.startswith(('AKASHA_','FEED_'))}]))\n")
    env = Environment(loader=FileSystemLoader(ROOT / "roles/akasha_collector/templates"),
                      undefined=StrictUndefined)
    launcher = tmp_path / "launcher"
    launcher.write_text(env.get_template("akasha-collector.j2").render(
        fleet_home=str(home), akasha_collector_url="https://akasha.ryzhkov.dev",
        akasha_collector_token_helper="/approved/helper",
        akasha_collector_node="/usr/bin/python3", akasha_collector_script=str(script)))
    config = home / ".config/chaldea"
    config.mkdir(parents=True)
    (config / "events.json").write_text(env.get_template("events.json.j2").render(
        fleet_home=str(home), akasha_collector_url="https://akasha.ryzhkov.dev",
        akasha_collector_token_helper="/approved/helper"))
    process_env = {**os.environ, "XDG_CONFIG_HOME": str(home / ".config"), "FEED_TOKEN": "must-not-reach-collector",
                   "FEED_KEY_FILE": "/never/open", "FEED_CONFIG": "/never/source"}
    with (state / "collector.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(["sh", str(launcher), "--dry-run"], env=process_env, capture_output=True, text=True)
        assert result.returncode != 0 and result.stdout == ""
    result = subprocess.run(["sh", str(launcher), "--dry-run"], env=process_env, capture_output=True, text=True, check=True)
    args, configured, inherited = json.loads(result.stdout)
    assert args == ["--dry-run"]
    assert configured["stateFile"] == str(state / "collector.db")
    assert configured["tokenHelper"] == "/approved/helper"
    assert inherited == {}


def test_pinned_collector_loads_canonical_events_config(tmp_path):
    pins = yaml.safe_load((ROOT / "inventory/group_vars/all/akasha-collector-runtime.yml").read_text())
    version = pins["akasha_collector_version"]
    url = "https://github.com/iryzhkov/chaldea/releases/download/" + version + "/chaldea-host.tar.gz"
    with urllib.request.urlopen(url, timeout=90) as response:
        archive = response.read()
    assert hashlib.sha256(archive).hexdigest() == pins["akasha_collector_sha256"]
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        member = bundle.extractfile("host/akasha-collector.mjs")
        assert member is not None
        script = tmp_path / "collector.mjs"
        script.write_bytes(member.read())
    config = tmp_path / "config/chaldea"
    config.mkdir(parents=True)
    template = Environment(loader=FileSystemLoader(ROOT / "roles/akasha_collector/templates"),
                           undefined=StrictUndefined).get_template("events.json.j2")
    values = json.loads(template.render(fleet_home=str(tmp_path),
        akasha_collector_url="https://akasha.example",
        akasha_collector_token_helper="/approved/helper"))
    path = config / "events.json"
    path.write_text(json.dumps(values))
    environment = {k: v for k, v in os.environ.items() if not k.startswith("AKASHA_")}
    environment["XDG_CONFIG_HOME"] = str(config.parent)
    def invoke():
        return subprocess.run(["node", str(script), "--dry-run"],
                              env=environment, capture_output=True, text=True)
    result = invoke()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert "deprecated configuration" not in result.stderr
    # A malformed canonical field must reach the actual collector's config parser.
    path.write_text(json.dumps(values | {"stateFile": []}))
    assert invoke().returncode != 0
