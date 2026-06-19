"""
checks/zeroth/sudo_hire_me.py — sudo-hire-me spec validation (zeroth mode)

Runs on a clone of the zeroth repo. Validates the spec files that
instances read remotely:
  - frameworks/sudo-hire-me/.scenarios.yml
  - frameworks/sudo-hire-me/scenarios/  (referenced files)
  - frameworks/sudo-hire-me/structure.yml

File presence checks are derived dynamically from structure.yml:
  - root_files  → each must exist under frameworks/sudo-hire-me/
  - directories → each top-level dir must exist under frameworks/sudo-hire-me/

This is giskard@zeroth — invoked via:
  python giskard.py --repo /path/to/zeroth --mode zeroth
================================================================================
"""

import yaml
from pathlib import Path
from core import run_check, Report

FRAMEWORK = "sudo-hire-me"
FRAMEWORK_DIR = f"frameworks/{FRAMEWORK}"


def _checks_from_structure(repo: Path) -> list[dict]:
    """
    Read frameworks/sudo-hire-me/structure.yml and derive file_exists checks.

    - root_files  → one check per file under frameworks/sudo-hire-me/
    - directories → one check per top-level directory key

    structure.yml is always checked first (hardcoded) because everything
    else depends on it being present.
    """
    structure_path = repo / FRAMEWORK_DIR / "structure.yml"
    # structure.yml itself is the anchor — always required
    base = [
        {
            "label": f"{FRAMEWORK_DIR}/structure.yml present",
            "proxy": "file_exists",
            "target": f"{FRAMEWORK_DIR}/structure.yml",
            "file": f"{FRAMEWORK_DIR}/structure.yml",
            "rule": f"{FRAMEWORK}/structure.yml",
        },
    ]

    if not structure_path.exists():
        return base

    try:
        data = yaml.safe_load(structure_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return base

    if not isinstance(data, dict):
        return base

    checks = list(base)

    # root_files: .agent.yml, .scenarios.yml, README.md, etc.
    for filename in (data.get("root_files") or []):
        target = f"{FRAMEWORK_DIR}/{filename}"
        checks.append({
            "label": f"{target} present",
            "proxy": "file_exists",
            "target": target,
            "file": target,
            "rule": f"{FRAMEWORK}/structure.yml",
        })

    # directories: hunt/, assets/, etc. — only the top-level key matters here
    for dir_key in (data.get("directories") or {}):
        # dir_key may have trailing slash: "hunt/" → normalise
        dir_name = dir_key.rstrip("/")
        target = f"{FRAMEWORK_DIR}/{dir_name}"
        checks.append({
            "label": f"{target}/ present",
            "proxy": "file_exists",
            "target": target,
            "file": f"{target}/",
            "rule": f"{FRAMEWORK}/structure.yml",
        })

    return checks


SCENARIOS_CONTENT_CHECKS = [
    {
        "label": f"{FRAMEWORK_DIR}/.scenarios.yml index format valid",
        "proxy": "scenarios_index_valid",
        "file": f"{FRAMEWORK_DIR}/.scenarios.yml",
        "rule": "rules/scenarios.yml",
    },
    {
        "label": f"{FRAMEWORK_DIR}/.scenarios.yml scenario files exist",
        "proxy": "scenarios_index_files_exist",
        "file": f"{FRAMEWORK_DIR}/.scenarios.yml",
        "rule": "rules/scenarios.yml",
    },
]


def run(repo: Path, report: Report) -> None:
    report.section("sudo-hire-me@zeroth — structure")
    for check in _checks_from_structure(repo):
        run_check(repo, check, report)

    report.section("sudo-hire-me@zeroth — scenarios")
    for check in SCENARIOS_CONTENT_CHECKS:
        run_check(repo, check, report)
