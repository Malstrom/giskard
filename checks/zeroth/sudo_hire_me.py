"""
checks/zeroth/sudo_hire_me.py — sudo-hire-me spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/sudo-hire-me/.scenarios.yml
  - frameworks/sudo-hire-me/scenarios/  (referenced files)
  - frameworks/sudo-hire-me/structure.yml
  - frameworks/sudo-hire-me/overview.yml

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth
================================================================================
"""

from pathlib import Path
from core import run_check, Report


STRUCTURE_CHECKS = [
    {
        "label": "frameworks/sudo-hire-me/.scenarios.yml present",
        "proxy": "file_exists",
        "target": "frameworks/sudo-hire-me/.scenarios.yml",
        "file": "frameworks/sudo-hire-me/.scenarios.yml",
        "rule": "sudo-hire-me/structure.yml",
    },
    {
        "label": "frameworks/sudo-hire-me/structure.yml present",
        "proxy": "file_exists",
        "target": "frameworks/sudo-hire-me/structure.yml",
        "file": "frameworks/sudo-hire-me/structure.yml",
        "rule": "sudo-hire-me/structure.yml",
    },
    {
        "label": "frameworks/sudo-hire-me/overview.yml present",
        "proxy": "file_exists",
        "target": "frameworks/sudo-hire-me/overview.yml",
        "file": "frameworks/sudo-hire-me/overview.yml",
        "rule": "sudo-hire-me/structure.yml",
    },
    {
        "label": "frameworks/sudo-hire-me/scenarios/ present",
        "proxy": "file_exists",
        "target": "frameworks/sudo-hire-me/scenarios",
        "file": "frameworks/sudo-hire-me/scenarios/",
        "rule": "sudo-hire-me/structure.yml",
    },
]

SCENARIOS_CONTENT_CHECKS = [
    {
        "label": "frameworks/sudo-hire-me/.scenarios.yml index format valid",
        "proxy": "scenarios_index_valid",
        "file": "frameworks/sudo-hire-me/.scenarios.yml",
        "rule": "rules/scenarios.yml",
    },
    {
        "label": "frameworks/sudo-hire-me/.scenarios.yml scenario files exist",
        "proxy": "scenarios_index_files_exist",
        "file": "frameworks/sudo-hire-me/.scenarios.yml",
        "rule": "rules/scenarios.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("sudo-hire-me@zeroth — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("sudo-hire-me@zeroth — scenarios")
    for check in SCENARIOS_CONTENT_CHECKS:
        run_check(repo, check, report)
