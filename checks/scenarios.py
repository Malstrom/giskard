"""
checks/scenarios.py — rules/scenarios.yml

Validates .scenarios.yml structure and emits a coverage warning
when .scenarios.yml is modified in a PR (Phase 2 of giskard#33).
"""

import os
import subprocess
import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

CHECKS = [
    {
        "label": ".scenarios.yml root key is required_scenarios",
        "proxy": "yaml_first_key",
        "file": ".scenarios.yml",
        "expected": "required_scenarios",
        "rule": "scenarios.yml",
    },
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
    {
        "label": "unknown_scenario is last",
        "proxy": "scenario_last",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    {
        "label": "handlers do not use say/ask/propose",
        "proxy": "scenario_no_forbidden_modules",
        "file": ".agent.yml",
        "rule": "scenarios.yml",
    },
]


def _get_scenarios(content: str) -> set:
    """Parse scenario names from .scenarios.yml content string."""
    try:
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            rs = parsed.get("required_scenarios") or {}
            return set(rs.keys()) if isinstance(rs, dict) else set()
    except Exception:
        pass
    return set()


def _check_scenario_coverage(repo: Path, report: Report) -> None:
    """
    If running in a GitHub Actions PR context (GITHUB_BASE_REF set),
    detect added or modified scenarios in .scenarios.yml and emit
    a warning prompting a giskard coverage review.

    Skipped silently on local runs.
    """
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if not base_ref:
        return  # not a PR context — skip silently

    scenarios_file = repo / ".scenarios.yml"
    if not scenarios_file.exists():
        return

    # fetch base content via git
    try:
        result = subprocess.run(
            ["git", "show", f"origin/{base_ref}:.scenarios.yml"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            # .scenarios.yml didn't exist on base branch — all scenarios are new
            base_scenarios = set()
        else:
            base_scenarios = _get_scenarios(result.stdout)
    except Exception:
        return  # git unavailable — skip silently

    current_scenarios = _get_scenarios(scenarios_file.read_text(encoding="utf-8"))
    added = sorted(current_scenarios - base_scenarios)

    if not added:
        return  # no new scenarios — no warning needed

    names = ", ".join(added)
    msg = (
        f"scenario change detected: {len(added)} new scenario(s): {names} — "
        f"verify giskard coverage in checks/frameworks/{{framework}}.py — "
        f"see Known gaps section in framework spec"
    )
    print(f"\n[giskard] ⚠️  {msg}")
    _gh_annotation("warning", f"giskard: {msg}", ".scenarios.yml")
    report.add(f"scenario coverage: {len(added)} new scenario(s) — review giskard checks", None, names)


def run(repo: Path, report: Report) -> None:
    report.section("scenarios")
    for check in CHECKS:
        run_check(repo, check, report)
    _check_scenario_coverage(repo, report)
