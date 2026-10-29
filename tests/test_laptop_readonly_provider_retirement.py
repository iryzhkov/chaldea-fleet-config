"""Current laptop defaults retire only the three superseded fixed readers.

Legacy binding tests explicitly select their historical qualification inputs.
This suite renders the actual default flags through Ansible and the maintained
closed validators, proving the retired admissions cannot fall back to ordinary
providers while the separately protected OpenCode profile stays unchanged.
"""
import json
import yaml

from test_laptop_jocasta_tooling import HOME, OPENCODE, ROOT, effective_session_maps, load, source

LEGACY = "chaldea_laptop_jocasta_legacy_sessions_enabled"
HOLO = "chaldea_laptop_holonet_catalog_enabled"
HNAME = "holonet-movies-catalog-claude"
RETIRED = [
    {"name": HNAME, "driver": "claude"},
    {"name": "jocasta-tooling-claude", "driver": "claude"},
    {"name": "jocasta-tooling-codex", "home": HOME + "/.cache/acl-codex-startup-f73bc687/home"},
]


def defaults():
    return {LEGACY: source()[LEGACY], HOLO: yaml.safe_load(
        (ROOT / "inventory/host_vars/laptop/chaldea-holonet-catalog.yml").read_text())[HOLO]}


def test_actual_defaults_remove_only_superseded_admissions_and_profiles():
    flags = defaults()
    assert flags == {LEGACY: False, HOLO: False}
    actual = effective_session_maps(flags, include_retired=True)
    for short in ("presets", "enrollments", "profiles"):
        assert actual["chaldea_client_session_" + short] == {
            OPENCODE: source()["chaldea_laptop_jocasta_" + short][OPENCODE]}
    assert actual["chaldea_client_session_ceilings"] == source()["chaldea_laptop_jocasta_ceilings"]
    assert actual["chaldea_client_session_profiles_absent"] == RETIRED
    load("session_enrollment").chaldea_session_enrollments(
        actual["chaldea_client_session_enrollments"], actual["chaldea_client_session_presets"],
        actual["chaldea_client_session_ceilings"], HOME)
    assert load("session_profiles").chaldea_session_profiles(
        actual["chaldea_client_session_profiles"], actual["chaldea_client_session_presets"],
        actual["chaldea_client_session_enrollments"], HOME, RETIRED)
    # There is no replacement preset on a broader ordinary provider.
    presets = actual["chaldea_client_session_presets"]
    assert set(p["instanceId"] for p in presets.values()) == {"opencode-jocasta-tooling"}
    assert all(p["delegate"] is False for p in presets.values())
    for name in (HNAME, "jocasta-tooling-claude", "jocasta-tooling-codex"):
        assert name not in presets


def test_explicit_rollback_inputs_never_deliver_and_retire_the_same_profile():
    rollback = effective_session_maps({LEGACY: True, HOLO: True}, include_retired=True)
    assert rollback["chaldea_client_session_profiles_absent"] == []
    assert set(rollback["chaldea_client_session_profiles"]) == {
        HNAME, "jocasta-tooling-claude", "jocasta-tooling-codex", OPENCODE}
    for flags, expected in [
        ({LEGACY: False, HOLO: True}, RETIRED[1:]),
        ({LEGACY: True, HOLO: False}, RETIRED[:1]),
    ]:
        values = effective_session_maps(flags, include_retired=True)
        assert values["chaldea_client_session_profiles_absent"] == expected
        assert not ({v["name"] for v in expected} & set(values["chaldea_client_session_profiles"]))


def test_cleanup_reuses_existing_file_inverse_and_preserves_interactive_opt_in():
    tasks = (ROOT / "roles/chaldea_client/tasks/session-profile-absent.yml").read_text()
    assert "Remove the launcher first, then the remaining role-owned files" in tasks
    assert "argv: [rmdir, --," in tasks
    # No credential or recursive HOME removal is introduced by the inventory.
    for value in RETIRED:
        assert set(value) in ({"name", "driver"}, {"name", "home"})
    ordinary = yaml.safe_load((ROOT / "inventory/host_vars/laptop/holonet-interactive.yml").read_text())
    assert ordinary == {"webmcp_interactive_holonet_enabled": True}
