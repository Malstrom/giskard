"""
checks/scenarios.py — rules/scenarios.yml

Validates .scenarios.yml structure.
"""

from pathlib import Path
from core import run_check, Report

CHECKS = [
    # Root key must be required_scenarios
    {
        "label": ".scenarios.yml root key is required_scenarios",
        "proxy": "yaml_first_key",
        "file": ".scenarios.yml",
        "expected": "required_scenarios",
        "rule": "scenarios.yml",
    },
    # Required scenarios present
    {
        "label": "session_start scenario present",
        "proxy": "scenario_present",
        "scenario": "session_start",
        "rule": "scenarios.yml",
    },
    {
        "label": "unknown_scenario present",
        "proxy": "scenario_present",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    # unknown_scenario must be last
    {
        "label": "unknown_scenario is last",
        "proxy": "scenario_last",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    # No forbidden modules in handler actions
    {
        "label": "handlers do not use say/ask/propose",
        "proxy": "scenario_no_forbidden_modules",
        "file": ".agent.yml",
        "rule": "scenarios.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("scenarios")
    for check in CHECKS:
        run_check(repo, check, report)
