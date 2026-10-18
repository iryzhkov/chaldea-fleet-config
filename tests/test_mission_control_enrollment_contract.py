"""Native registry/helper composition against an exact hosted-source fixture pin."""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

import pytest

from test_akasha_enrollment import client, compose, public_inputs

# SOURCE FIXTURE ONLY. Never an installed production artifact/version/SHA.
HOSTED_SOURCE = "7dfc9c7fee8efaf0e4e96bf65df3dad983644108"


@pytest.fixture(scope="module")
def hosted(client, tmp_path_factory):
    destination = tmp_path_factory.mktemp("hosted-source-fixture") / "client"
    # Reuse released dependencies; overlay only the pinned source fixture.
    shutil.copytree(client, destination)
    raw = urllib.request.urlopen(
        "https://codeload.github.com/iryzhkov/chaldea/tar.gz/" + HOSTED_SOURCE, timeout=90).read()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        prefix = "chaldea-" + HOSTED_SOURCE + "/src/"
        files = [m for m in archive.getmembers() if m.isfile() and m.name.startswith(prefix)]
        assert files
        for member in files:
            relative = Path(member.name.removeprefix(prefix))
            assert not relative.is_absolute() and ".." not in relative.parts
            path = destination / "src" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(member).read())
    return destination


def test_exact_publisher_reader_registry_helpers_and_ceiling(hosted, client, tmp_path):
    packet = dict(publisher_uid=1000, reader_uid=23017, read_sources=["agent-a--mission-control"])
    result = compose(hosted, public_inputs() | dict(mission_control=packet))
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    mc = [r for r in rendered["registry"] if r["profile"].startswith("mission-control-")]
    assert mc == [
        dict(issuer="chaldea:agent-a", source="agent-a.mission-control", host="agent-a",
             source_id="agent-a--mission-control", profile="mission-control-publisher",
             project="chaldea", mode="service", kinds=["agent_status"]),
        dict(issuer="chaldea:omarchy-normandy", source="mission-control-reader", host="omarchy-normandy",
             source_id="omarchy-normandy--mission-control-reader", profile="mission-control-reader",
             project="chaldea", mode="service", kinds=["agent_status"],
             mission_control_read_sources=["agent-a--mission-control"])]
    grants = [g for rows in rendered["grants"].values() for g in rows if g["profile"].startswith("mission-control-")]
    assert grants == [
        dict(uid=1000, audience="akasha", action="append", source="agent-a.mission-control",
             host="agent-a", kind="agent_status", profile="mission-control-publisher", project="chaldea"),
        dict(uid=23017, audience="akasha", action="read", source="mission-control-reader",
             host="omarchy-normandy", kind="agent_status", profile="mission-control-reader", project="chaldea")]
    for issuer in rendered["issuers"]:
        for ceiling in issuer["ceilings"]:
            if ceiling["profile"].startswith("mission-control-"):
                assert ceiling["grants"] == [dict(resource=ceiling["source"],
                    actions=["append" if ceiling["profile"] == "mission-control-publisher" else "read"])]
    # The unchanged released helper accepts the dedicated read/append grants.
    program = """
      import {helperConfig} from './src/access/helper.ts';
      const grants=JSON.parse(process.argv[1]);
      for(const g of grants) helperConfig({issuer:{uid:995,key_file:'/fixture/key',name:'chaldea:'+g.host,kid:'fixture'},
        state_file:'/fixture/state',bundle_file:'/fixture/bundle',anchor_file:'/fixture/anchors',
        clock_health_file:'/fixture/clock',grants:[g]});
    """
    checked = subprocess.run(["node", "--input-type=module", "-e", program, json.dumps(grants)],
                             cwd=client, text=True, capture_output=True)
    assert checked.returncode == 0, checked.stderr
    # Exercise the real new registry decoder's service-only scope denials.
    program = """
      import {Authorization} from './src/akasha/auth.ts';
      const registry=JSON.parse(process.argv[1]);
      new Authorization(registry,null,null);
    """
    for mutation in (dict(mode="operator"), dict(profile="fleet-reader"), dict(project="other"),
                     dict(kinds=["tool_call"]), dict(global_read=True), dict(quota_fleet_read=True),
                     dict(mission_control_read_sources=["foreign"])):
        invalid = copy.deepcopy(rendered["registry"])
        reader = next(r for r in invalid if r["profile"] == "mission-control-reader")
        reader.update(mutation)
        denied = subprocess.run(["node", "--input-type=module", "-e", program, json.dumps(invalid)],
                                cwd=hosted, text=True, capture_output=True)
        assert denied.returncode != 0, mutation
