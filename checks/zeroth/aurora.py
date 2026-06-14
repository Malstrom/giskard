"""
checks/zeroth/aurora.py — aurora spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/aurora/.scenarios.yml
  - frameworks/aurora/templates/
  - frameworks/aurora/structure.yml

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth --framework aurora

Note: scenario content validation is NOT done here (no REQUIRED_SCENARIOS).
Only structure and file presence are checked, consistent with dojo.py.
================================================================================
"""

from pathlib import Path
from core import run_check, Report

# Source of truth: frameworks/aurora/structure.yml — templates section
REQUIRED_TEMPLATES = [
    "aurora.yml",
    "agent.yml",
    "scenarios.yml",
    "log.yml",
    "log_index.yml",
    "inbox.yml",
    "contact.yml",
    "client_context.yml",
    "playbook.yml",
]

STRUCTURE_CHECKS = [
    {
        "label": "frameworks/aurora/.scenarios.yml present",
        "proxy": "file_exists",
        "target": "frameworks/aurora/.scenarios.yml",
        "file": "frameworks/aurora/.scenarios.yml",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/templates/ present",
        "proxy": "file_exists",
        "target": "frameworks/aurora/templates",
        "file": "frameworks/aurora/templates/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/templates/ has all required files",
        "proxy": "dir_has_templates",
        "target": "frameworks/aurora/templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/structure.yml present",
        "proxy": "file_exists",
        "target": "frameworks/aurora/structure.yml",
        "file": "frameworks/aurora/structure.yml",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/onboarding.yml present",
        "proxy": "file_exists",
        "target": "frameworks/aurora/onboarding.yml",
        "file": "frameworks/aurora/onboarding.yml",
        "rule": "aurora/structure.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("aurora@zeroth — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)
