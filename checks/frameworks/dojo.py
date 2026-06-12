"""
checks/frameworks/dojo.py — dojo framework checks

================================================================================
DOJO FRAMEWORK SPEC
Source: zeroth/frameworks/dojo/structure.yml + .scenarios.yml + templates/
Last updated: 2026-06-12
================================================================================

Section order (top-down, most general to most specific):

  dojo — structure
    Required root files: .agent.yml, .scenarios.yml, .registry.yml, .gakusei.yml
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
    1. kiroku/nikki/ filenames match YYYY-MM-DD_{subject}_{type}.yml
    2. last_session.subject → kata/{subject}/ must exist
    3. nikki subject → gakusei.subjects
    4. makimono subject → gakusei.subjects
    5. nikki subject → kata/{subject}/ exists
    6. nikki → makimono consistency: every nikki subject must have makimono/{subject}.yml

================================================================================
"""

import re
import yaml
from collections import defaultdict
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

NIKKI_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_(.+)_[^_]+\.yml$")


def _read_yaml_file(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _nikki_subjects(nikki_dir: Path) -> set:
    """Extract unique subjects from valid nikki filenames."""
    subjects = set()
    for f in nikki_dir.iterdir():
        if f.suffix != ".yml":
            continue
        m = NIKKI_PATTERN.match(f.name)
        if m:
            subjects.add(m.group(1))
    return subjects


def _check_refs(repo: Path, report: Report) -> None:
    gakusei = _read_yaml_file(repo / ".gakusei.yml")
    gakusei_subjects = set(gakusei.get("subjects", {}).keys()) if isinstance(gakusei.get("subjects"), dict) else set()
    last_session = gakusei.get("last_session") or {}
    ls_subject = last_session.get("subject") if isinstance(last_session, dict) else None

    nikki_dir = repo / "kiroku" / "nikki"
    makimono_dir = repo / "kiroku" / "makimono"

    # --- 1. nikki filename pattern ---
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

    # --- 2. last_session.subject → kata/{subject}/ exists ---
    if ls_subject:
        kata_dir = repo / "kata" / ls_subject
        if not kata_dir.is_dir():
            report.add(f"last_session.subject '{ls_subject}' has no kata/{ls_subject}/ directory", False,
                       f"kata/{ls_subject}/ not found", rule="dojo/refs.yml")
            _gh_annotation("error", f"giskard ERROR: kata/{ls_subject}/ missing", ".gakusei.yml")
        else:
            report.add(f"last_session.subject '{ls_subject}' → kata/{ls_subject}/ exists", True)
    else:
        report.add("last_session.subject empty — skipping kata ref check", None)

    # --- 3. nikki subject → gakusei.subjects ---
    if nikki_dir.is_dir() and gakusei_subjects:
        nikki_subs = _nikki_subjects(nikki_dir)
        unknown = sorted(nikki_subs - gakusei_subjects)
        if unknown:
            detail = "subjects in nikki not in .gakusei.yml ← " + ", ".join(unknown)
            report.add("nikki subjects not declared in .gakusei.yml", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: nikki subject not in gakusei", str(nikki_dir))
        elif nikki_subs:
            report.add(f"all nikki subjects declared in .gakusei.yml ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no nikki files found — skipping nikki→gakusei check", None)
    else:
        report.add("skipping nikki→gakusei check (no nikki dir or no subjects)", None)

    # --- 4. makimono subject → gakusei.subjects ---
    if makimono_dir.is_dir() and gakusei_subjects:
        makimono_files = [f for f in makimono_dir.iterdir() if f.suffix == ".yml"]
        unknown_maki = sorted(f.stem for f in makimono_files if f.stem not in gakusei_subjects)
        if unknown_maki:
            detail = "makimono files with no matching subject in .gakusei.yml ← " + ", ".join(unknown_maki)
            report.add("makimono subjects not declared in .gakusei.yml", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: makimono subject not in gakusei", str(makimono_dir))
        elif makimono_files:
            report.add(f"all makimono subjects declared in .gakusei.yml ({len(makimono_files)} files)", True)
        else:
            report.add("no makimono files found — skipping makimono→gakusei check", None)
    else:
        report.add("skipping makimono→gakusei check (no makimono dir or no subjects)", None)

    # --- 5. nikki subject → kata/{subject}/ exists ---
    if nikki_dir.is_dir():
        nikki_subs = _nikki_subjects(nikki_dir)
        missing_kata = defaultdict(list)
        for sub in sorted(nikki_subs):
            if not (repo / "kata" / sub).is_dir():
                missing_kata[sub].append(f"kata/{sub}/")
        if missing_kata:
            for sub, paths in sorted(missing_kata.items()):
                detail = "kata dir missing ← " + ", ".join(paths)
                report.add(f"nikki subject '{sub}' has no kata/{sub}/ directory", False, detail, rule="dojo/refs.yml")
                _gh_annotation("error", f"giskard ERROR: kata/{sub}/ missing for nikki subject", str(nikki_dir))
        elif nikki_subs:
            report.add(f"all nikki subjects have kata/ directory ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no nikki files found — skipping nikki→kata check", None)
    else:
        report.add("kiroku/nikki/ not found — skipping nikki→kata check", None)

    # --- 6. nikki → makimono consistency ---
    if nikki_dir.is_dir() and makimono_dir.is_dir():
        nikki_subs = _nikki_subjects(nikki_dir)
        makimono_subjects = {f.stem for f in makimono_dir.iterdir() if f.suffix == ".yml"}
        missing_maki = sorted(nikki_subs - makimono_subjects)
        if missing_maki:
            detail = "nikki subjects with no makimono file ← " + ", ".join(
                f"kiroku/makimono/{s}.yml" for s in missing_maki
            )
            report.add("nikki subjects missing corresponding makimono file", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: makimono missing for nikki subject",
                           f"kiroku/makimono/{missing_maki[0]}.yml")
        elif nikki_subs:
            report.add(f"all nikki subjects have a makimono file ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no nikki files found — skipping nikki→makimono check", None)
    else:
        report.add("skipping nikki→makimono check (nikki or makimono dir missing)", None)


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
