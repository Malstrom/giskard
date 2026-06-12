"""
checks/zeroth/dojo.py — dojo spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/dojo/.scenarios.yml
  - frameworks/dojo/templates/
  - frameworks/dojo/structure.yml

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth --framework dojo
================================================================================
"""

import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

REQUIRED_TEMPLATES = [
    "kata.yml",
    "kiroku_nikki.yml",
    "kiroku_makimono.yml",
    "shinsa.yml",
]

REQUIRED_SCENARIOS = [
    "session_start",
    "study_open",
    "randori",
    "quiz",
    "shinsa",
    "level_up",
    "unknown_scenario",
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


def _parse_yaml(path: Path) -> dict:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _check_scenarios(repo: Path, report: Report) -> None:
    scenarios_path = repo / "frameworks" / "dojo" / ".scenarios.yml"
    if not scenarios_path.exists():
        report.add("frameworks/dojo/.scenarios.yml not found — skipping scenario checks", None)
        return

    sc = _parse_yaml(scenarios_path)
    rs = sc.get("required_scenarios", {}) or {}
    keys = list(rs.keys())

    for name in REQUIRED_SCENARIOS:
        present = name in rs
        report.add(
            f"scenario '{name}' present",
            present,
            rule="dojo/scenarios.yml",
            file="frameworks/dojo/.scenarios.yml",
        )
        if not present:
            _gh_annotation("error", f"giskard ERROR: scenario '{name}' missing",
                           "frameworks/dojo/.scenarios.yml")

    # unknown_scenario must be last
    if keys:
        is_last = keys[-1] == "unknown_scenario"
        report.add(
            "scenario 'unknown_scenario' is last",
            is_last,
            f"last is '{keys[-1]}'",
            rule="dojo/scenarios.yml",
            file="frameworks/dojo/.scenarios.yml",
        )

    # study_open must have >= 2 input_sources
    if "study_open" in rs:
        count = len((rs["study_open"] or {}).get("input_sources", []))
        report.add(
            "scenario 'study_open' has >= 2 input_sources",
            count >= 2,
            f"{count}/2 input_sources",
            rule="dojo/scenarios.yml",
            file="frameworks/dojo/.scenarios.yml",
        )


def run(repo: Path, report: Report) -> None:
    report.section("dojo@zeroth — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("dojo@zeroth — scenarios")
    _check_scenarios(repo, report)
