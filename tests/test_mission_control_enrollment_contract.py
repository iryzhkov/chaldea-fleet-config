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


def test_pc_existing_collector_prospective_native_contract(hosted, client, tmp_path):
    from test_akasha_enrollment import ROOT
    from test_token_helper import render
    active = ROOT / "access-trust/issuer-grants.json"
    before = active.read_bytes()
    # Exercise the prospective grant even after its approved ceiling is published.
    fixture_issuers = json.loads(before)
    pc_ceiling = dict(audience="akasha", profile="mission-control-publisher", project="chaldea",
        source="omarchy-pc.mission-control",
        grants=[dict(resource="omarchy-pc.mission-control", actions=["append"])])
    for row in fixture_issuers:
        if row["issuer"] == "chaldea:omarchy-pc":
            row["ceilings"] = [c for c in row["ceilings"] if c != pc_ceiling]
    fixture_file = tmp_path / "before-pc-status.json"
    fixture_file.write_text(json.dumps(fixture_issuers))
    data = public_inputs() | dict(laptop_quota=True, pc_quota_reader=True)
    packet = dict(publisher_uid=1000, reader_uid=940, read_sources=["agent-a--mission-control"])
    old = compose(hosted, data | dict(mission_control=packet), existing=fixture_file)
    assert old.returncode == 0, old.stderr
    omitted = compose(hosted, data | dict(mission_control=packet | dict(pc_publisher_uid=None)), existing=fixture_file)
    assert omitted.returncode == 0 and omitted.stdout == old.stdout
    pc_packet = packet | dict(pc_publisher_uid=1000,
        read_sources=["agent-a--mission-control", "omarchy-pc--mission-control"])
    result = compose(hosted, data | dict(mission_control=pc_packet), existing=fixture_file)
    assert result.returncode == 0, result.stderr
    baseline, proposed = json.loads(old.stdout), json.loads(result.stdout)
    pc = next(r for r in proposed["registry"] if r["source"] == "omarchy-pc.mission-control")
    assert pc == dict(issuer="chaldea:omarchy-pc", source="omarchy-pc.mission-control",
        host="omarchy-pc", source_id="omarchy-pc--mission-control", profile="mission-control-publisher",
        project="chaldea", mode="service", kinds=["agent_status"])
    assert len(proposed["registry"]) == len(baseline["registry"]) + 1
    assert all(row in proposed["registry"] for row in baseline["registry"] if row["profile"] != "mission-control-reader")
    reader = next(r for r in proposed["registry"] if r["profile"] == "mission-control-reader")
    assert reader["mission_control_read_sources"] == pc_packet["read_sources"]
    for host, grants in baseline["grants"].items():
        assert proposed["grants"][host][:len(grants)] == grants
        assert len(proposed["grants"][host]) == len(grants) + (host == "omarchy-pc")
    for row in baseline["issuers"]:
        actual = next(r for r in proposed["issuers"] if r["issuer"] == row["issuer"] and r["kid"] == row["kid"])
        assert {k:v for k,v in actual.items() if k != "ceilings"} == {k:v for k,v in row.items() if k != "ceilings"}
        assert actual["ceilings"][:len(row["ceilings"])] == row["ceilings"]
        assert len(actual["ceilings"]) == len(row["ceilings"]) + (row["issuer"] == "chaldea:omarchy-pc")
    grant = proposed["grants"]["omarchy-pc"][-1]
    assert grant["uid"] == 1000 and grant["kind"] == "agent_status"
    sudoers = render("sudoers.j2", dict(chaldea_token_helper_grants=[grant]))
    assert "#1000 ALL=(chaldea-issuer) NOPASSWD: NOSETENV: /usr/local/libexec/chaldea-token-helper-issuer --audience akasha --action append --source omarchy-pc.mission-control --host omarchy-pc --kind agent_status" in sudoers
    assert "*" not in sudoers and "/bin/sh" not in sudoers
    for invalid in (dict(pc_publisher_uid=938), dict(pc_publisher_uid="1000"), dict(pc_publisher_uid=True),
                    dict(read_sources=["agent-a--mission-control"]), dict(publisher_uid=None),
                    dict(read_sources=["agent-a--mission-control", "foreign"])):
        denied = compose(hosted, data | dict(mission_control=pc_packet | invalid), existing=fixture_file)
        assert denied.returncode != 0, invalid
    assert active.read_bytes() == before

def test_remaining_collectors_native_uid_scope_and_preservation(hosted, tmp_path):
    import hashlib
    import os
    # Exact source fixture, never a production release pin. ROOT publishes C first.
    auth_url = "https://raw.githubusercontent.com/iryzhkov/chaldea/ee52539baab3fd141ee69b1338a038888fb891b5/src/akasha/auth.ts"
    local = os.environ.get("MC_CANONICAL_AUTH_FIXTURE")
    auth = Path(local).read_bytes() if local else urllib.request.urlopen(auth_url, timeout=90).read()
    assert hashlib.sha256(auth).hexdigest() == "f4c25bc180f5d4cf90efe651bf7b077f20e16c7054733e37df22bfe709241513"
    canonical = tmp_path / "canonical-client"
    shutil.copytree(hosted, canonical)
    (canonical / "src/akasha/auth.ts").write_bytes(auth)
    from test_akasha_enrollment import ROOT
    active = ROOT / "access-trust/issuer-grants.json"
    source = json.loads(active.read_text())
    assert len(source) == 6
    previous = copy.deepcopy(source)
    for host in ("agent-b", "omarchy-macbook-air-igor"):
        ceiling = dict(audience="akasha", profile="mission-control-publisher", project="chaldea",
            source=host + ".mission-control",
            grants=[dict(resource=host + ".mission-control", actions=["append"])])
        row = next(r for r in previous if r["issuer"] == "chaldea:" + host)
        assert row["kid"] == host + "-2026-10-cutover"
        assert row["ceilings"].count(ceiling) == 1
        assert row["ceilings"][-1] == ceiling
        row["ceilings"].remove(ceiling)
    fixture_file = tmp_path / "before-remaining-status.json"
    fixture_file.write_text(json.dumps(previous))
    data = public_inputs() | dict(pc_reader=True, pc_quota=True, laptop_quota=False, pc_quota_reader=False)
    packet: dict = dict(publisher_uid=1000, pc_publisher_uid=1000, reader_uid=940,
                  read_sources=["agent-a--mission-control", "omarchy-pc--mission-control"])
    baseline = compose(canonical, data | dict(mission_control=packet), existing=fixture_file)
    assert baseline.returncode == 0, baseline.stderr
    before = json.loads(baseline.stdout)
    for b, laptop in [(True, False), (False, True), (True, True)]:
        selected: dict = packet | dict(agent_b_publisher_uid=1000 if b else None,
                                 laptop_publisher_uid=1001 if laptop else None,
                                 read_sources=packet["read_sources"] +
                                    (["agent-b--mission-control"] if b else []) +
                                    (["omarchy-macbook-air-igor--mission-control"] if laptop else []))
        result = compose(canonical, data | dict(mission_control=selected), existing=fixture_file)
        assert result.returncode == 0, result.stderr
        after = json.loads(result.stdout)
        hosts = (["agent-b"] if b else []) + (["omarchy-macbook-air-igor"] if laptop else [])
        assert len(after["registry"]) == len(before["registry"]) + len(hosts)
        assert all(row in after["registry"] for row in before["registry"] if row["profile"] != "mission-control-reader")
        reader = next(row for row in after["registry"] if row["profile"] == "mission-control-reader")
        assert reader["mission_control_read_sources"] == selected["read_sources"]
        for host, old in before["grants"].items():
            assert after["grants"][host][:len(old)] == old
            assert len(after["grants"][host]) == len(old) + (host in hosts)
            if host in hosts:
                assert after["grants"][host][-1] == dict(uid=1001 if host.startswith("omarchy-macbook") else 1000,
                    audience="akasha", action="append", source=host + ".mission-control", host=host,
                    kind="agent_status", profile="mission-control-publisher", project="chaldea")
        for old in before["issuers"]:
            row = next(r for r in after["issuers"] if r["issuer"] == old["issuer"])
            assert {k:v for k,v in row.items() if k != "ceilings"} == {k:v for k,v in old.items() if k != "ceilings"}
            assert row["ceilings"][:len(old["ceilings"])] == old["ceilings"]
            assert len(row["ceilings"]) == len(old["ceilings"]) + (old["issuer"].removeprefix("chaldea:") in hosts)
        if b and laptop:
            assert after["issuers"] == source
            # The actual source is idempotent under the same native composition.
            actual = compose(canonical, data | dict(mission_control=selected))
            assert actual.returncode == 0, actual.stderr
            assert json.loads(actual.stdout) == after
        if evidence := os.environ.get("MC_REMAINING_RENDER_DIR"):
            Path(evidence).mkdir(parents=True, exist_ok=True)
            (Path(evidence) / f"b{int(b)}-l{int(laptop)}.json").write_text(result.stdout)
            if b and laptop:
                (Path(evidence) / "inputs.json").write_text(json.dumps(data | dict(mission_control=selected)))
                (Path(evidence) / "baseline.json").write_text(baseline.stdout)
        for invalid in [dict(agent_b_publisher_uid=1001), dict(laptop_publisher_uid=1000),
                        dict(read_sources=selected["read_sources"] + ["foreign"]),
                        dict(read_sources=selected["read_sources"] * 2),
                        dict(read_sources=list(reversed(selected["read_sources"]))),
                        dict(unknown_host="other")]:
            assert compose(canonical, data | dict(mission_control=selected | invalid), existing=fixture_file).returncode != 0
