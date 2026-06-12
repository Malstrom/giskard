"""
checks/zeroth/aurora.py — aurora spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/aurora/.scenarios.yml
  - frameworks/aurora/templates/
  - frameworks/aurora/structure.yml

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth --framework aurora
================================================================================
"""

import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

REQUIRED_TEMPLATES = [
    "inbox.yml",
    "log.yml",
    "log_index.yml",
    "contact.yml",
    "client_context.yml",
    "playbook.yml",
    "output_csv.md",
    "output_email.md",
    "output_report.md",
]

REQUIRED_SCENARIOS = [
    "session_start",
    "inbox_open",
    "inbox_triage",
    "client_open",
    "work_open",
    "reindex_check",
    "unknown_scenario",
]

STRUCTURE_CHECKS = [
    {
        "label": "frameworks/aurora/.scenarios.yml not found",
        "proxy": "file_exists",
        "target": "frameworks/aurora/.scenarios.yml",
        "file": "frameworks/aurora/.scenarios.yml",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/templates/ not found",
        "proxy": "file_exists",
        "target": "frameworks/aurora/templates",
        "file": "frameworks/aurora/templates/",
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/templates/ missing required files",
        "proxy": "dir_has_templates",
        "target": "frameworks/aurora/templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "aurora/structure.yml",
    },
    {
        "label": "frameworks/aurora/structure.yml not found",
        "proxy": "file_exists",
        "target": "frameworks/aurora/structure.yml",
        "file": "frameworks/aurora/structure.yml",
        "rule": "aurora/structure.yml",
    },
]


def _parse_yaml(path: Path) -> dict:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _check_scenarios(repo: Path, report: Report) -> None:
    scenarios_path = repo / "frameworks" / "aurora" / ".scenarios.yml"
    if not scenarios_path.exists():
        report.add("frameworks/aurora/.scenarios.yml not found — skipping scenario checks", None)
        return

    sc = _parse_yaml(scenarios_path)
    rs = sc.get("required_scenarios", {}) or {}
    keys = list(rs.keys())

    for name in REQUIRED_SCENARIOS:
        present = name in rs
        report.add(
            f"scenario '{name}' present",
            present,
            rule="aurora/scenarios.yml",
            file="frameworks/aurora/.scenarios.yml",
        )
        if not present:
            _gh_annotation("error", f"giskard ERROR: scenario '{name}' missing",
                           "frameworks/aurora/.scenarios.yml")

    # unknown_scenario must be last
    if keys:
        is_last = keys[-1] == "unknown_scenario"
        report.add(
            "scenario 'unknown_scenario' is last",
            is_last,
            f"last is '{keys[-1]}'",
            rule="aurora/scenarios.yml",
            file="frameworks/aurora/.scenarios.yml",
        )

    # inbox_open must have >= 2 input_sources
    if "inbox_open" in rs:
        count = len((rs["inbox_open"] or {}).get("input_sources", []))
        report.add(
            "scenario 'inbox_open' has >= 2 input_sources",
            count >= 2,
            f"{count}/2 input_sources",
            rule="aurora/scenarios.yml",
            file="frameworks/aurora/.scenarios.yml",
        )


def run(repo: Path, report: Report) -> None:
    report.section("aurora@zeroth — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("aurora@zeroth — scenarios")
    _check_scenarios(repo, report)
