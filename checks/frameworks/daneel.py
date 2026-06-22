"""
checks/frameworks/daneel.py — giskard checks for the daneel framework.

Validates playbook index consistency for all client playbook directories
and the root playbooks/ directory.

Consumer side lives in zeroth: frameworks/daneel/checks.yml + rules/playbooks.yml
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    {
        "label": "clients/*/playbooks/_index.yml consistent",
        "proxy": "playbook_index_consistent",
        "target": "clients/*/playbooks",
        "is_client_dir": True,
        "rule": "rules/playbooks.yml",
    },
    {
        "label": "playbooks/_index.yml consistent",
        "proxy": "playbook_index_consistent",
        "target": "playbooks",
        "is_client_dir": False,
        "rule": "rules/playbooks.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("daneel — playbooks")
    for check in CHECKS:
        run_check(repo, check, report)
