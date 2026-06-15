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


def _required_templates_from_structure(repo: Path) -> list[str]:
    """
    Derive the expected template filenames from structure.yml.

    For each entry in structure.yml that has a 'template' field pointing
    to 'frameworks/dojo/templates/{filename}', extract {filename}.
    This way REQUIRED_TEMPLATES never needs to be maintained separately.
    """
    structure_path = repo / "frameworks" / "dojo" / "structure.yml"
    if not structure_path.exists():
        return []
    try:
        data = yaml.safe_load(structure_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []

    seen = set()
    result = []
    for meta in (data.get("structure") or {}).values():
        template_path = (meta or {}).get("template", "")
        if "/templates/" in template_path:
            filename = template_path.split("/templates/")[-1]
            if filename and filename not in seen:
                seen.add(filename)
                result.append(filename)
    return result


STRUCTURE_CHECKS_BASE = [
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
    for check in STRUCTURE_CHECKS_BASE:
        run_check(repo, check, report)

    # Derive required templates dynamically from structure.yml
    required_templates = _required_templates_from_structure(repo)
    run_check(repo, {
        "label": "frameworks/dojo/templates/ missing required files",
        "proxy": "dir_has_templates",
        "target": "frameworks/dojo/templates",
        "required_files": required_templates,
        "rule": "dojo/structure.yml",
    }, report)
