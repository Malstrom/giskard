"""
checks/zeroth/dojo.py — dojo spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/dojo/.scenarios.yml
  - frameworks/dojo/templates/
  - frameworks/dojo/structure.yml

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth
================================================================================
"""

import yaml
from pathlib import Path
from core import run_check, Report

REQUIRED_TEMPLATES = [
    "kata.yml",
    "kiroku_nikki.yml",
    "kiroku_makimono.yml",
    "shinsa.yml",
]

STRUCTURE_CHECKS = [
    {
        "label": "frameworks/dojo/.scenarios.yml not found",
        "proxy": "file_exists",
        "target": "frameworks/dojo/.scenarios.yml",
        "file": "frameworks/dojo/.scenarios.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "frameworks/dojo/templates/ not found",
        "proxy": "file_exists",
        "target": "frameworks/dojo/templates",
        "file": "frameworks/dojo/templates/",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "frameworks/dojo/templates/ missing required files",
        "proxy": "dir_has_templates",
        "target": "frameworks/dojo/templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "dojo/structure.yml",
    },
    {
        "label": "frameworks/dojo/structure.yml not found",
        "proxy": "file_exists",
        "target": "frameworks/dojo/structure.yml",
        "file": "frameworks/dojo/structure.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "frameworks/dojo/onboarding.yml not found",
        "proxy": "file_exists",
        "target": "frameworks/dojo/onboarding.yml",
        "file": "frameworks/dojo/onboarding.yml",
        "rule": "dojo/structure.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("dojo@zeroth — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)
