"""
checks/frameworks/dojo.py — dojo framework checks

================================================================================
DOJO FRAMEWORK SPEC
Source: zeroth/frameworks/dojo/structure.yml + .scenarios.yml + templates/
Last updated: 2026-06-11
================================================================================

Section order (top-down, most general to most specific):

  dojo — structure
    Required root files: .agent.yml, .scenarios.yml, .registry.yml,
    .gakusei.yml, onboarding.yml
    Required dirs: kata/, kiroku/makimono/, kiroku/nikki/, templates/
    Required templates: kata.yml, kiroku_nikki.yml, kiroku_makimono.yml, shinsa.yml
    .gakusei.yml required keys: name, language, subjects, last_session

  dojo — scenarios
    Required scenarios: session_start, study_open, randori, quiz, shinsa,
    level_up, unknown_scenario (must be last)
    study_open must declare at least 2 input_sources

  dojo — files
    kiroku/nikki/????-??-??_*.yml → templates/kiroku_nikki.yml
    kiroku/makimono/*.yml          → templates/kiroku_makimono.yml
    Skipped if no generated files exist.

  dojo — refs
    kiroku/nikki/ filenames match YYYY-MM-DD_{subject}_{type}.yml
    .gakusei.yml last_session.subject → kata/{subject}/ must exist

================================================================================
"""

import re
import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

REQUIRED_TEMPLATES = [
    "kata.yml",
    "kiroku_nikki.yml",
    "kiroku_makimono.yml",
    "shinsa.yml",
]

STRUCTURE_CHECKS = [
    {
        "label": ".agent.yml not found",
        "proxy": "file_exists",
        "target": ".agent.yml",
        "file": ".agent.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".scenarios.yml not found",
        "proxy": "file_exists",
        "target": ".scenarios.yml",
        "file": ".scenarios.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".registry.yml not found",
        "proxy": "file_exists",
        "target": ".registry.yml",
        "file": ".registry.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml not found",
        "proxy": "file_exists",
        "target": ".gakusei.yml",
        "file": ".gakusei.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "onboarding.yml not found",
        "proxy": "file_exists",
        "target": "onboarding.yml",
        "file": "onboarding.yml",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "kata/ directory not found",
        "proxy": "file_exists",
        "target": "kata",
        "file": "kata/",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "kiroku/makimono/ directory not found",
        "proxy": "file_exists",
        "target": "kiroku/makimono",
        "file": "kiroku/makimono/",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "kiroku/nikki/ directory not found",
        "proxy": "file_exists",
        "target": "kiroku/nikki",
        "file": "kiroku/nikki/",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "templates/ directory not found",
        "proxy": "file_exists",
        "target": "templates",
        "file": "templates/",
        "rule": "dojo/structure.yml",
    },
    {
        "label": "templates/ missing required dojo files",
        "proxy": "dir_has_templates",
        "target": "templates",
        "required_files": REQUIRED_TEMPLATES,
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'name' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "name",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'language' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "language",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'subjects' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "subjects",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'last_session' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "last_session",
        "rule": "dojo/structure.yml",
    },
]

SCENARIO_CHECKS = [
    {
        "label": "scenario 'session_start' not found",
        "proxy": "scenario_present",
        "scenario": "session_start",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'study_open' not found",
        "proxy": "scenario_present",
        "scenario": "study_open",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'randori' not found",
        "proxy": "scenario_present",
        "scenario": "randori",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'quiz' not found",
        "proxy": "scenario_present",
        "scenario": "quiz",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'shinsa' not found",
        "proxy": "scenario_present",
        "scenario": "shinsa",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'level_up' not found",
        "proxy": "scenario_present",
        "scenario": "level_up",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'unknown_scenario' not found",
        "proxy": "scenario_present",
        "scenario": "unknown_scenario",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'unknown_scenario' is not last",
        "proxy": "scenario_last",
        "scenario": "unknown_scenario",
        "rule": "dojo/scenarios.yml",
    },
    {
        "label": "scenario 'study_open' has fewer than 2 input_sources",
        "proxy": "scenario_input_sources",
        "scenario": "study_open",
        "min_count": 2,
        "rule": "dojo/scenarios.yml",
    },
]

FILE_KEY_CHECKS = [
    {
        "label": "kiroku/nikki files: keys missing vs templates/kiroku_nikki.yml",
        "proxy": "generated_files_match_template",
        "glob": "kiroku/nikki/????-??-??_*.yml",
        "template": "templates/kiroku_nikki.yml",
        "rule": "dojo/files.yml",
    },
    {
        "label": "kiroku/makimono files: keys missing vs templates/kiroku_makimono.yml",
        "proxy": "generated_files_match_template",
        "glob": "kiroku/makimono/*.yml",
        "template": "templates/kiroku_makimono.yml",
        "rule": "dojo/files.yml",
    },
]

NIKKI_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_.+\.yml$")


def _read_yaml_file(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _check_refs(repo: Path, report: Report) -> None:
    """
    Referential integrity checks:
    1. kiroku/nikki/ filenames match YYYY-MM-DD_{subject}_{type}.yml
    2. .gakusei.yml last_session.subject -> kata/{subject}/ must exist
    """
    # 1 — nikki filename pattern
    nikki_dir = repo / "kiroku" / "nikki"
    if nikki_dir.is_dir():
        bad_names = [
            str(f.relative_to(repo))
            for f in nikki_dir.iterdir()
            if f.suffix == ".yml" and not NIKKI_PATTERN.match(f.name)
        ]
        if bad_names:
            detail = "invalid filename pattern ← " + ", ".join(sorted(bad_names))
            report.add("kiroku/nikki filenames: pattern YYYY-MM-DD_{subject}_{type}.yml not respected", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: kiroku/nikki invalid filename", bad_names[0])
        else:
            nikki_files = [f for f in nikki_dir.iterdir() if f.suffix == ".yml"]
            report.add(f"all kiroku/nikki filenames match pattern ({len(nikki_files)} files)", True)
    else:
        report.add("kiroku/nikki/ not found — skipping filename check", None)

    # 2 — last_session.subject -> kata/{subject}/ exists
    gakusei = _read_yaml_file(repo / ".gakusei.yml")
    last_session = gakusei.get("last_session") or {}
    subject = last_session.get("subject") if isinstance(last_session, dict) else None
    if subject:
        kata_dir = repo / "kata" / subject
        if not kata_dir.is_dir():
            report.add(f"last_session.subject '{subject}' has no kata/{subject}/ directory", False,
                       f"kata/{subject}/ not found", rule="dojo/refs.yml")
            _gh_annotation("error", f"giskard ERROR: kata/{subject}/ missing", ".gakusei.yml")
        else:
            report.add(f"last_session.subject '{subject}' → kata/{subject}/ exists", True)
    else:
        report.add("last_session.subject empty — skipping kata ref check", None)


def run(repo: Path, report: Report) -> None:
    report.section("dojo — structure")
    for check in STRUCTURE_CHECKS:
        run_check(repo, check, report)

    report.section("dojo — scenarios")
    for check in SCENARIO_CHECKS:
        run_check(repo, check, report)

    report.section("dojo — files")
    for check in FILE_KEY_CHECKS:
        run_check(repo, check, report)

    report.section("dojo — refs")
    _check_refs(repo, report)
