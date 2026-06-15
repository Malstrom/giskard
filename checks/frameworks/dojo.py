"""
checks/frameworks/dojo.py — dojo framework checks (instance mode)

================================================================================
DOJO INSTANCE CHECKS
Validates the student instance repo only.
Spec files (.scenarios.yml, templates/) live in zeroth and are NOT checked here.
Source: zeroth/frameworks/dojo/structure.yml
Last updated: 2026-06-15
================================================================================

Section order:

  dojo — structure
    Required root files: .agent.yml, .gakusei.yml, gakusei.md
    Required dirs: kata/, kiroku/makimono/, kiroku/nikki/
    .gakusei.yml required keys: student_name, last_session, topics, goals
    NOTE: if .gakusei.yml is absent, key checks emit WARNING (onboarding
    not yet run) instead of FAIL.

  dojo — files
    kiroku/nikki/????-??-??_*_*.yml → templates/kiroku_nikki.yml (if present locally)
    kiroku/makimono/????-??-??_*_passed.yml → templates/kiroku_makimono.yml (if present locally)
    Skipped if template not found locally.

  dojo — refs
    0. kiroku/nikki/ contains only .yml files
    1. kiroku/nikki/ filenames match YYYY-MM-DD_{topic}_{type}.yml
       type must be one of: study | shinsa | goal_shinsa
    2. last_session.topic → kata/{topic}.md must exist
    3. nikki topic → topics key in .gakusei.yml
    4. makimono goal_slug → goals key in .gakusei.yml
    5. nikki topic → kata/{topic}.md exists
    6. nikki → makimono consistency (WARNING — makimono only created at goal_shinsa pass)

================================================================================
"""

import re
import yaml
from collections import defaultdict
from pathlib import Path
from core import run_check, Report, _gh_annotation

_IGNORED_NAMES = {".keep", ".gitkeep"}

# Nikki type values defined in structure.yml
_NIKKI_VALID_TYPES = {"study", "shinsa", "goal_shinsa"}

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
        "label": "gakusei.md not found",
        "proxy": "file_exists",
        "target": "gakusei.md",
        "file": "gakusei.md",
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

# Keys required by zeroth/frameworks/dojo/templates/.gakusei.yml
GAKUSEI_KEY_CHECKS = [
    {
        "label": ".gakusei.yml missing 'student_name' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "student_name",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'last_session' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "last_session",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'topics' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "topics",
        "rule": "dojo/structure.yml",
    },
    {
        "label": ".gakusei.yml missing 'goals' field",
        "proxy": "yaml_key_exists",
        "file": ".gakusei.yml",
        "key": "goals",
        "rule": "dojo/structure.yml",
    },
]

# Globs aligned to structure.yml filename_pattern values
FILE_KEY_CHECKS = [
    {
        "label": "kiroku/nikki files: keys missing vs templates/kiroku_nikki.yml",
        "proxy": "generated_files_match_template",
        "glob": "kiroku/nikki/????-??-??_*_*.yml",
        "template": "templates/kiroku_nikki.yml",
        "rule": "dojo/files.yml",
    },
    {
        "label": "kiroku/makimono files: keys missing vs templates/kiroku_makimono.yml",
        "proxy": "generated_files_match_template",
        "glob": "kiroku/makimono/????-??-??_*_passed.yml",
        "template": "templates/kiroku_makimono.yml",
        "rule": "dojo/files.yml",
    },
]

# Pattern: YYYY-MM-DD_{topic}_{type}.yml — topic may contain underscores
# Capture group 1: topic (greedy, then last underscore splits type)
NIKKI_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)_([^_]+)\.yml$")

# Pattern: YYYY-MM-DD_{goal_slug}_passed.yml
MAKIMONO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_(.+)_passed\.yml$")


def _read_yaml_file(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _nikki_topics(nikki_dir: Path) -> set:
    """Extract unique topics from valid nikki filenames."""
    topics = set()
    for f in nikki_dir.iterdir():
        if f.suffix != ".yml" or f.name in _IGNORED_NAMES:
            continue
        m = NIKKI_PATTERN.match(f.name)
        if m:
            topics.add(m.group(2))  # group 2 is the topic
    return topics


def _makimono_goals(makimono_dir: Path) -> set:
    """Extract unique goal slugs from valid makimono filenames."""
    goals = set()
    for f in makimono_dir.iterdir():
        if f.suffix != ".yml" or f.name in _IGNORED_NAMES:
            continue
        m = MAKIMONO_PATTERN.match(f.name)
        if m:
            goals.add(m.group(1))  # group 1 is the goal_slug
    return goals


def _check_refs(repo: Path, report: Report) -> None:
    gakusei = _read_yaml_file(repo / ".gakusei.yml")

    # topics is a dict: topic_slug -> {status, readiness_status, ...}
    topics_raw = gakusei.get("topics") or {}
    gakusei_topics = set(topics_raw.keys()) if isinstance(topics_raw, dict) else set()

    # goals is a dict: goal_slug -> {declared_on, status, ...}
    goals_raw = gakusei.get("goals") or {}
    gakusei_goals = set(goals_raw.keys()) if isinstance(goals_raw, dict) else set()

    last_session = gakusei.get("last_session") or {}
    ls_topic = last_session.get("topic") if isinstance(last_session, dict) else None

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

    # --- 1. nikki filename pattern + valid type ---
    if nikki_dir.is_dir():
        bad_names = []
        bad_types = []
        for f in nikki_dir.iterdir():
            if f.name in _IGNORED_NAMES or f.suffix != ".yml":
                continue
            m = NIKKI_PATTERN.match(f.name)
            if not m:
                bad_names.append(str(f.relative_to(repo)))
            elif m.group(3) not in _NIKKI_VALID_TYPES:
                bad_types.append(f"{f.name} (type='{m.group(3)}'")
        if bad_names:
            detail = "invalid filename pattern <- " + ", ".join(sorted(bad_names))
            report.add(
                "kiroku/nikki filenames: pattern YYYY-MM-DD_{topic}_{type}.yml not respected",
                False, detail, rule="dojo/refs.yml"
            )
            _gh_annotation("error", "giskard ERROR: kiroku/nikki invalid filename", bad_names[0])
        elif bad_types:
            detail = "invalid type value (must be study|shinsa|goal_shinsa) <- " + ", ".join(sorted(bad_types))
            report.add("kiroku/nikki filenames: invalid type value", False, detail, rule="dojo/refs.yml")
        else:
            nikki_files = [f for f in nikki_dir.iterdir() if f.suffix == ".yml" and f.name not in _IGNORED_NAMES]
            report.add(f"all kiroku/nikki filenames match pattern ({len(nikki_files)} files)", True)
    else:
        report.add("kiroku/nikki/ not found — skipping filename check", None)

    # --- 2. last_session.topic → kata/{topic}.md must exist ---
    if ls_topic:
        kata_file = repo / "kata" / f"{ls_topic}.md"
        if not kata_file.is_file():
            report.add(
                f"last_session.topic '{ls_topic}' has no kata/{ls_topic}.md file",
                False, f"kata/{ls_topic}.md not found", rule="dojo/refs.yml"
            )
            _gh_annotation("error", f"giskard ERROR: kata/{ls_topic}.md missing", ".gakusei.yml")
        else:
            report.add(f"last_session.topic '{ls_topic}' → kata/{ls_topic}.md exists", True)
    else:
        report.add("last_session.topic empty — skipping kata ref check", None)

    # --- 3. nikki topic → topics key in .gakusei.yml ---
    if nikki_dir.is_dir() and gakusei_topics:
        nikki_tops = _nikki_topics(nikki_dir)
        unknown = sorted(nikki_tops - gakusei_topics)
        if unknown:
            detail = "topics in nikki not in .gakusei.yml <- " + ", ".join(unknown)
            report.add("nikki topics not declared in .gakusei.yml", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: nikki topic not in gakusei.topics", str(nikki_dir))
        elif nikki_tops:
            report.add(f"all nikki topics declared in .gakusei.yml ({len(nikki_tops)} topics)", True)
        else:
            report.add("no valid nikki files found — skipping nikki→gakusei check", None)
    else:
        report.add("skipping nikki→gakusei check (no nikki dir or no topics declared)", None)

    # --- 4. makimono goal_slug → goals key in .gakusei.yml ---
    if makimono_dir.is_dir() and gakusei_goals:
        maki_goals = _makimono_goals(makimono_dir)
        unknown_maki = sorted(maki_goals - gakusei_goals)
        if unknown_maki:
            detail = "makimono files with no matching goal in .gakusei.yml <- " + ", ".join(unknown_maki)
            report.add("makimono goals not declared in .gakusei.yml", False, detail, rule="dojo/refs.yml")
            _gh_annotation("error", "giskard ERROR: makimono goal not in gakusei.goals", str(makimono_dir))
        elif maki_goals:
            report.add(f"all makimono goals declared in .gakusei.yml ({len(maki_goals)} goals)", True)
        else:
            report.add("no makimono files found — skipping makimono→gakusei check", None)
    else:
        report.add("skipping makimono→gakusei check (no makimono dir or no goals declared)", None)

    # --- 5. nikki topic → kata/{topic}.md exists ---
    if nikki_dir.is_dir():
        nikki_tops = _nikki_topics(nikki_dir)
        missing_kata = sorted(t for t in nikki_tops if not (repo / "kata" / f"{t}.md").is_file())
        if missing_kata:
            for topic in missing_kata:
                detail = f"kata/{topic}.md not found"
                report.add(f"nikki topic '{topic}' has no kata/{topic}.md file", False, detail, rule="dojo/refs.yml")
                _gh_annotation("error", f"giskard ERROR: kata/{topic}.md missing for nikki topic", str(nikki_dir))
        elif nikki_tops:
            report.add(f"all nikki topics have kata/ file ({len(nikki_tops)} topics)", True)
        else:
            report.add("no valid nikki files found — skipping nikki→kata check", None)
    else:
        report.add("kiroku/nikki/ not found — skipping nikki→kata check", None)

    # --- 6. nikki → makimono consistency (WARNING only) ---
    # Makimono files are created only at goal_shinsa pass — topic-level nikki
    # without a makimono is the normal pre-goal state.
    if nikki_dir.is_dir() and makimono_dir.is_dir():
        nikki_goal_topics = set()
        for f in nikki_dir.iterdir():
            if f.suffix != ".yml" or f.name in _IGNORED_NAMES:
                continue
            m = NIKKI_PATTERN.match(f.name)
            if m and m.group(3) == "goal_shinsa":
                nikki_goal_topics.add(m.group(2))
        maki_goals = _makimono_goals(makimono_dir)
        missing_maki = sorted(nikki_goal_topics - maki_goals)
        if missing_maki:
            detail = "goal_shinsa nikki with no passing makimono <- " + ", ".join(
                f"kiroku/makimono/YYYY-MM-DD_{g}_passed.yml" for g in missing_maki
            )
            report.add("goal_shinsa nikki sessions missing corresponding makimono", None, detail, rule="dojo/refs.yml")
        elif nikki_goal_topics:
            report.add(f"all goal_shinsa sessions have a makimono file ({len(nikki_goal_topics)} goals)", True)
        else:
            report.add("no goal_shinsa nikki found — skipping nikki→makimono check", None)
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
