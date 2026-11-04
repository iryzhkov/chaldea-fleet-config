"""Exercise metadata and drift checks on disposable managed skill trees."""
import importlib.util
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("skill_audit", ROOT / "tools/check-agent-skills.py")
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_metadata_rejects_mismatch_and_empty_description(tmp_path):
    folder = tmp_path / "sample"
    folder.mkdir()
    entry = folder / "SKILL.md"
    entry.write_text("---\nname: other\ndescription: valid\n---\n")
    assert any("name must match" in error for error in audit.check(tmp_path, ["sample"]))
    entry.write_text("---\nname: sample\ndescription: ''\n---\n")
    assert any("nonempty" in error for error in audit.check(tmp_path, ["sample"]))


def test_drift_and_missing_reference(tmp_path):
    source = tmp_path / "source"
    folder = source / "sample"
    folder.mkdir(parents=True)
    entry = folder / "SKILL.md"
    entry.write_text("---\nname: sample\ndescription: valid\n---\n")
    home = tmp_path / "home"
    installed = home / ".agents/skills/sample"
    shutil.copytree(folder, installed)
    assert not audit.check(source, ["sample"], home, [".agents/skills"])
    (installed / "SKILL.md").write_text("changed")
    assert any("differs" in error for error in audit.check(source, ["sample"], home, [".agents/skills"]))
    entry.write_text(entry.read_text() + "[required](references/missing.md)\n")
    assert any("missing or escaping" in error for error in audit.check(source, ["sample"]))
