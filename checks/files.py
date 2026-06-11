"""
checks/files.py — zeroth laws: required files

Validates that all mandatory structural files are present.
These checks run first — they are framework-agnostic.
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    {
        "label": ".agent.yml exists",
        "proxy": "file_exists",
        "target": ".agent.yml",
        "file": ".agent.yml",
        "rule": "files.yml",
    },
    {
        "label": ".registry.yml exists",
        "proxy": "file_exists",
        "target": ".registry.yml",
        "file": ".registry.yml",
        "rule": "files.yml",
    },
    {
        "label": ".scenarios.yml exists",
        "proxy": "file_exists",
        "target": ".scenarios.yml",
        "file": ".scenarios.yml",
        "rule": "files.yml",
    },
    {
        "label": "README.md exists",
        "proxy": "file_exists",
        "target": "README.md",
        "file": "README.md",
        "rule": "files.yml",
    },
    {
        "label": ".github/workflows/ exists",
        "proxy": "file_exists",
        "target": ".github/workflows",
        "file": ".github/workflows",
        "rule": "files.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("zeroth — files")
    for check in CHECKS:
        run_check(repo, check, report)
