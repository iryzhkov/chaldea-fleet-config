#!/usr/bin/env python3
"""Validate managed skill metadata, references and optional installed bytes."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

import yaml


def check(source, names, home=None, directories=()):
    errors = []
    for name in names:
        folder = source / name
        entry = folder / "SKILL.md"
        try:
            text = entry.read_text()
            frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
            if frontmatter is None:
                raise ValueError("missing YAML frontmatter")
            metadata = yaml.safe_load(frontmatter.group(1))
            if not isinstance(metadata, dict) or metadata.get("name") != name:
                raise ValueError("name must match skill directory")
            description = metadata.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError("description must be nonempty text")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{entry}: {exc}")
            continue
        for document in folder.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if ":" in link or link.startswith("#"):
                    continue
                target = (document.parent / link.split("#", 1)[0]).resolve()
                if not target.is_relative_to(folder.resolve()) or not target.is_file():
                    errors.append(f"{document}: missing or escaping reference {link}")
        if home is None:
            continue
        for directory in directories:
            installed = home / directory / name
            if installed.is_symlink() or not installed.is_dir():
                errors.append(f"{installed}: expected managed directory")
                continue
            for node in installed.rglob("*"):
                if node.is_symlink():
                    errors.append(f"{node}: unexpected symlink in managed skill")
            expected = {p.relative_to(folder): p for p in folder.rglob("*") if p.is_file()}
            actual = {p.relative_to(installed): p for p in installed.rglob("*") if p.is_file()}
            for relative in sorted(expected.keys() | actual.keys()):
                destination = installed / relative
                if (relative not in expected or relative not in actual
                        or destination.is_symlink()
                        or hashlib.sha256(expected[relative].read_bytes()).digest()
                        != hashlib.sha256(actual[relative].read_bytes()).digest()):
                    errors.append(f"{destination}: installed content differs from managed source")
    if home is not None:
        for directory in directories:
            root = home / directory
            if root.exists():
                for item in root.iterdir():
                    if item.is_symlink() and not item.exists():
                        errors.append(f"{item}: dangling skill link")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, help="also audit this installed home, read-only")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    defaults = yaml.safe_load((root / "roles/agent_config/defaults/main.yml").read_text())
    errors = check(root / "roles/agent_config/files/skills",
                   defaults["agent_config_skills"], args.home,
                   defaults["agent_config_skill_dirs"])
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Managed skill metadata and references valid"
              + ("; installed skills match" if args.home else ""))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
