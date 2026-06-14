"""
checks/frameworks/dojo.py — dojo framework checks (instance mode)

================================================================================
DOJO INSTANCE CHECKS
Validates the student instance repo only.
Spec files (.scenarios.yml, templates/) live in zeroth and are NOT checked here.
Source: zeroth/frameworks/dojo/structure.yml
Last updated: 2026-06-14
================================================================================

Section order:

  dojo — structure
    Required root files: .agent.yml, .gakusei.yml
    Required dirs: kata/, kiroku/makimono/, kiroku/nikki/
    .gakusei.yml required keys: name, language, subjects, last_session
    NOTE: if .gakusei.yml is absent, key checks emit WARNING (onboarding
    not yet run) instead of FAIL.

  dojo — files
    kiroku/nikki/????-??-??_*.yml → templates/kiroku_nikki.yml (if present locally)
    kiroku/makimono/*.yml          → templates/kiroku_makimono.yml (if present locally)
    Skipped if template not found locally.

  dojo — refs
    0. kiroku/nikki/ contains only .yml files
    1. kiroku/nikki/ filenames match YYYY-MM-DD_{subject}_{type}.yml
    2. last_session.subject → kata/{subject}/ must exist
    3. nikki subject → gakusei.subjects
    4. makimono subject → gakusei.subjects
    5. nikki subject → kata/{subject}/ exists
    6. nikki → makimono consistency (WARNING — makimono only created at level_up)

================================================================================
"""

import re
import yaml
from collections import defaultdict
from pathlib import Path
from core import run_check, Report, _gh_annotation

_IGNORED_NAMES = {".keep", ".gitkeep"}

STRUCTURE_CHECKS_NO_GAKUSEI = [
    {
        "label": ".agent.yml not found",
        "proxy": "file_exists",
        "target": ".agent.yml",
        "file": ".agent.yml",
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
]

GAKUSEI_KEY_CHECKS = [
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

    # --- 0. kiroku/nikki/ must contain only .yml files ---
    if nikki_dir.is_dir():
        wrong_ext = sorted(
            str(f.relative_to(repo))
            for f in nikki_dir.iterdir()
            if f.is_file() and f.name not in _IGNORED_NAMES and f.suffix != ".yml"
        )
        if wrong_ext:
            detail = "non-.yml files found <- " + ", ".join(wrong_ext)
            report.add("kiroku/nikki/ contains non-.yml files", False, detail, rule="dojo/refs.yml")
            for path in wrong_ext:
                _gh_annotation("error", f"giskard ERROR: kiroku/nikki file must be .yml, got {path}", path)
        else:
            report.add("kiroku/nikki/ contains only .yml files", True)

    # --- 1. nikki filename pattern ---
    if nikki_dir.is_dir():
        bad_names = [
            str(f.relative_to(repo))
            for f in nikki_dir.iterdir()
            if f.suffix == ".yml" and not NIKKI_PATTERN.match(f.name)
        ]
        if bad_names:
            detail = "invalid filename pattern <- " + ", ".join(sorted(bad_names))
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
            detail = "subjects in nikki not in .gakusei.yml <- " + ", ".join(unknown)
            report.add("nikki subjects not declared in .gakusei.yml", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: nikki subject not in gakusei", str(nikki_dir))
        elif nikki_subs:
            report.add(f"all nikki subjects declared in .gakusei.yml ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no valid nikki files found — skipping nikki→gakusei check", None)
    else:
        report.add("skipping nikki→gakusei check (no nikki dir or no subjects)", None)

    # --- 4. makimono subject → gakusei.subjects ---
    if makimono_dir.is_dir() and gakusei_subjects:
        makimono_files = [f for f in makimono_dir.iterdir() if f.suffix == ".yml"]
        unknown_maki = sorted(f.stem for f in makimono_files if f.stem not in gakusei_subjects)
        if unknown_maki:
            detail = "makimono files with no matching subject in .gakusei.yml <- " + ", ".join(unknown_maki)
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
                detail = "kata dir missing <- " + ", ".join(paths)
                report.add(f"nikki subject '{sub}' has no kata/{sub}/ directory", False, detail, rule="dojo/refs.yml")
                _gh_annotation("error", f"giskard ERROR: kata/{sub}/ missing for nikki subject", str(nikki_dir))
        elif nikki_subs:
            report.add(f"all nikki subjects have kata/ directory ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no valid nikki files found — skipping nikki→kata check", None)
    else:
        report.add("kiroku/nikki/ not found — skipping nikki→kata check", None)

    # --- 6. nikki → makimono consistency (WARNING only) ---
    # Makimono files are created only at level_up, not at study_open.
    # A dojo with nikki but no makimono is a valid pre-level-up state.
    if nikki_dir.is_dir() and makimono_dir.is_dir():
        nikki_subs = _nikki_subjects(nikki_dir)
        makimono_subjects = {f.stem for f in makimono_dir.iterdir() if f.suffix == ".yml"}
        missing_maki = sorted(nikki_subs - makimono_subjects)
        if missing_maki:
            detail = "nikki subjects with no makimono yet <- " + ", ".join(
                f"kiroku/makimono/{s}.yml" for s in missing_maki
            )
            report.add("nikki subjects missing corresponding makimono file", None, detail, rule="dojo/refs.yml")
        elif nikki_subs:
            report.add(f"all nikki subjects have a makimono file ({len(nikki_subs)} subjects)", True)
        else:
            report.add("no valid nikki files found — skipping nikki→makimono check", None)
    else:
        report.add("skipping nikki→makimono check (nikki or makimono dir missing)", None)


def run(repo: Path, report: Report) -> None:
    report.section("dojo — structure")
    for check in STRUCTURE_CHECKS_NO_GAKUSEI:
        run_check(repo, check, report)

    gakusei_path = repo / ".gakusei.yml"
    if not gakusei_path.exists():
        report.add(".gakusei.yml absent — onboarding not yet run", None,
                   "run the dojo onboarding scenario to generate this file",
                   rule="dojo/structure.yml", file=".gakusei.yml")
    else:
        for check in GAKUSEI_KEY_CHECKS:
            run_check(repo, check, report)

    report.section("dojo — files")
    for check in FILE_KEY_CHECKS:
        run_check(repo, check, report)

    report.section("dojo — refs")
    _check_refs(repo, report)
