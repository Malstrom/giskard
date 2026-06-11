"""
checks/connections.py — rules/connections.yml

Validates .registry.yml structure and connection fields.
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    # Required top-level fields
    {
        "label": ".registry.yml has 'framework' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "framework",
        "rule": "connections.yml",
    },
    {
        "label": ".registry.yml has 'version' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "version",
        "rule": "connections.yml",
    },
    {
        "label": ".registry.yml has 'connections' field",
        "proxy": "yaml_key_exists",
        "file": ".registry.yml",
        "key": "connections",
        "rule": "connections.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("connections")
    for check in CHECKS:
        run_check(repo, check, report)
