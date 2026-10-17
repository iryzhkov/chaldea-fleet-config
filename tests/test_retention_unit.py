"""The rendered chaldea-retention.service must hand the script arguments it accepts."""

import shlex
from pathlib import Path

import jinja2
import pytest

from test_retention import retention

TEMPLATE = Path(__file__).resolve().parents[1] / "roles/retention/templates/chaldea-retention.service.j2"


def render(mise_prune):
    # Ansible's template module renders with trim_blocks enabled, which is what
    # swallowed the newline after an {% endif %} in round 2 of the review.
    env = jinja2.Environment(trim_blocks=True, keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    env.filters["bool"] = bool  # stand-in for Ansible's filter; the test only passes real booleans
    return env.from_string(TEMPLATE.read_text()).render(
        retention_script="/home/u/.local/bin/chaldea-retention",
        retention_protect_hours=24,
        retention_worktree_root="/home/u/.t3/worktrees",
        retention_worktree_max_age_days=14,
        retention_worktree_budget_gb=20,
        retention_worktree_pressure_age_days=3,
        retention_disposable_ignored=["node_modules", "target"],
        retention_tmp_dir="/home/u/.cache/tmp",
        retention_tmp_max_age_days=3,
        retention_go_cache_max_gb=10,
        retention_mise_prune=mise_prune,
    )


def exec_start(unit):
    lines = unit.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("ExecStart="))
    command = []
    for line in lines[start:]:
        command.append(line.rstrip("\\").strip())
        if not line.endswith("\\"):
            break
    return shlex.split(" ".join(command).removeprefix("ExecStart=")), lines


@pytest.mark.parametrize("mise_prune", [True, False])
def test_rendered_unit_arguments_parse(mise_prune):
    argv, lines = exec_start(render(mise_prune))
    assert "Nice=19" in lines and "IOSchedulingClass=idle" in lines
    assert argv[:5] == ["%h/.local/bin/chaldea-timer-report", "run", "--job", "chaldea-retention", "--"]
    assert "OnFailure=chaldea-timer-failure@chaldea-retention.service" in lines
    args = retention.parse_args(argv[6:])
    assert args.go_cache_max_gb == 10
    assert ("--no-mise-prune" in argv) is (not mise_prune)
