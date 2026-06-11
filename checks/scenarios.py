"""
checks/scenarios.py — zeroth laws: scenario catalog

Validates .scenarios.yml structure and mandatory scenarios.
These checks are framework-agnostic.

Label convention: labels describe what is WRONG when the check fails.
Proxy result False = the condition described in the label is true (something missing/wrong).
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    {
        "label": ".scenarios.yml root key is not required_scenarios",
        "proxy": "yaml_first_key",
        "file": ".scenarios.yml",
        "expected": "required_scenarios",
        "rule": "scenarios.yml",
    },
    {
        "label": "scenario session_start not found",
        "proxy": "scenario_present",
        "scenario": "session_start",
        "rule": "scenarios.yml",
    },
    {
        "label": "scenario unknown_scenario not found",
        "proxy": "scenario_present",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    {
        "label": "unknown_scenario is not last",
        "proxy": "scenario_last",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    {
        "label": "handlers use forbidden modules (say/ask/propose)",
        "proxy": "scenario_no_forbidden_modules",
        "file": ".agent.yml",
        "rule": "scenarios.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("zeroth — scenarios")
    for check in CHECKS:
        run_check(repo, check, report)
