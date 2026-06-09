#!/usr/bin/env python3
"""
giskard — framework validator for the Malstrom ecosystem
Reads zeroth checklists and validates a repo against them.

Usage:
  python giskard.py --framework dojo --repo /path/to/repo
"""

import argparse
import re
import sys
import yaml
from pathlib import Path

ZEROTH_CHECKLISTS = {
    "dojo": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/dojo/checklist.yml",
    "tensho": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/tensho/checklist.yml",
    "sudo-hire-me": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/sudo-hire-me/checklist.yml",
}

REQUIRED_TEMPLATES = {
    "dojo": [
        "kata.md",
        "kiroku_session.md",
        "shinsa.md",
    ]
}

AGENT_FILES = {".agent.yml", ".registry.yml"}


def load_checklist(framework: str) -> dict:
    import urllib.request
    url = ZEROTH_CHECKLISTS.get(framework)
    if not url:
        print(f"[giskard] ERROR: unknown framework '{framework}'")
        sys.exit(1)
    with urllib.request.urlopen(url) as response:
        return yaml.safe_load(response.read().decode())


def check_structure(repo: Path, items: list, framework: str) -> list:
    results = []
    for item in items:
        if "exists in root" in item:
            name = item.split(" exists in root")[0].strip()
            results.append((item, (repo / name).exists()))

        elif "exists with all required templates" in item:
            dirname = item.split(" exists with")[0].strip().rstrip("/")
            dir_path = repo / dirname
            if not dir_path.is_dir():
                results.append((item, False))
                continue
            required = REQUIRED_TEMPLATES.get(framework, [])
            missing = [f for f in required if not (dir_path / f).exists()]
            if missing:
                print(f"    missing templates: {', '.join(missing)}")
            results.append((item, len(missing) == 0))

        elif "exists with at least one subject subfolder" in item:
            dirname = item.split(" exists with")[0].strip().rstrip("/")
            dir_path = repo / dirname
            if not dir_path.is_dir():
                results.append((item, False))
                continue
            subfolders = [d for d in dir_path.iterdir() if d.is_dir()]
            results.append((item, len(subfolders) > 0))

        elif item.endswith(" exists"):
            dirname = item.split(" exists")[0].strip().rstrip("/")
            results.append((item, (repo / dirname).exists()))

        elif "does NOT exist" in item:
            name = item.split(" does NOT exist")[0].strip()
            results.append((item, not (repo / name).exists()))

        else:
            results.append((item, None))
    return results


def check_strict_root(repo: Path, config: dict) -> list:
    allowed = set(config.get("allowed", []))
    violations = [item.name for item in repo.iterdir() if item.name not in allowed]
    if violations:
        print(f"    unexpected in root: {', '.join(sorted(violations))}")
        return [("no unexpected files in root", False)]
    return [("no unexpected files in root", True)]


def check_dynamic_dirs(repo: Path, config: dict) -> list:
    results = []
    for dirname, rules in config.items():
        dir_path = repo / Path(dirname.rstrip("/"))
        pattern = rules.get("pattern", "")
        regex = rules.get("regex", "")
        allow_empty = rules.get("allow_empty", True)
        required_files = rules.get("required_files", [])
        label = f"{dirname} files match pattern '{pattern}'"

        if not dir_path.is_dir():
            results.append((label, None))
            continue

        for rf in required_files:
            rf_path = dir_path / rf
            results.append((f"{dirname}/{rf} exists", rf_path.exists()))

        files = [
            f for f in dir_path.iterdir()
            if f.is_file() and f.name not in AGENT_FILES
        ]

        if not files:
            results.append((label, True if allow_empty else None))
            continue

        if not regex:
            results.append((label, None))
            continue

        violations = [f.name for f in files if not re.match(regex, f.name)]
        if violations:
            print(f"    {dirname} naming violations: {', '.join(sorted(violations))}")
            results.append((label, False))
        else:
            results.append((label, True))

    return results


def _load_agent(repo: Path):
    agent_path = repo / ".agent.yml"
    if not agent_path.exists():
        return "", {}
    content = agent_path.read_text()
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        print(f"    [giskard] WARN: .agent.yml parse error: {e}")
        parsed = {}
    return content, parsed if isinstance(parsed, dict) else {}


def _load_scenarios(repo: Path):
    sc_path = repo / ".scenarios.yml"
    if not sc_path.exists():
        return "", {}
    content = sc_path.read_text()
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        parsed = {}
    return content, parsed if isinstance(parsed, dict) else {}


def check_agent_yml(repo: Path, sections: dict) -> list:
    content, parsed = _load_agent(repo)
    if not content:
        all_items = [item for items in sections.values() for item in items]
        return [(item, False) for item in all_items]

    sc_content, sc_parsed = _load_scenarios(repo)
    scenario_keys = []
    rs = sc_parsed.get("required_scenarios", {})
    if isinstance(rs, dict):
        scenario_keys = list(rs.keys())

    results = []

    for item in sections.get("block_order", []):
        if "connector_check is the first block" in item:
            lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
            passed = lines[0].strip().startswith("connector_check") if lines else False
            results.append((item, passed))
        elif "post_action_hook is present and declares after_every_state_change" in item:
            pah = parsed.get("post_action_hook", {})
            passed = isinstance(pah, dict) and "after_every_state_change" in pah
            results.append((item, passed))
        elif " is present" in item:
            block_name = item.split(" is present")[0].strip()
            results.append((item, block_name in parsed))
        else:
            results.append((item, None))

    gl = parsed.get("global", {}) or {}
    for item in sections.get("global", []):
        if "global.language reads from .gakusei.yml" in item:
            lang_val = str(gl.get("language", ""))
            results.append((item, ".gakusei.yml" in lang_val or "gakusei" in lang_val))
        elif "global.pr_strategy is batch_per_session" in item:
            results.append((item, gl.get("pr_strategy") == "batch_per_session"))
        elif "global.merge_strategy is squash" in item:
            results.append((item, gl.get("merge_strategy") == "squash"))
        elif "global.dedup_scope is current_session" in item:
            results.append((item, gl.get("dedup_scope") == "current_session"))
        else:
            results.append((item, None))

    for item in sections.get("scenarios", []):
        if "scenarios_file" in item:
            results.append((item, parsed.get("scenarios", {}).get("scenarios_file") is not None))
        elif "does NOT exist" in item:
            name = item.split(" does NOT exist")[0].strip()
            results.append((item, name not in scenario_keys))
        elif "is present and is the last scenario" in item:
            name = item.split(" is present")[0].strip()
            results.append((item, scenario_keys[-1] == name if scenario_keys else False))
        elif "scenario is present in .scenarios.yml" in item:
            # handle: "{name} scenario is present in .scenarios.yml with all N input_sources"
            name = item.split(" scenario is present")[0].strip()
            present = name in scenario_keys
            if "with all" in item and "input_sources" in item:
                # check input_sources count
                match = re.search(r"all (\d+) input_sources", item)
                expected = int(match.group(1)) if match else 0
                sc = rs.get(name, {}) if isinstance(rs, dict) else {}
                actual = len(sc.get("input_sources", []))
                if present and actual < expected:
                    print(f"    {name} has {actual} input_sources, expected {expected}")
                results.append((item, present and actual >= expected))
            else:
                results.append((item, present))
        else:
            results.append((item, None))

    handlers = parsed.get("handlers", {}) or {}
    for item in sections.get("handlers", []):
        if "session_end handler is present" in item:
            results.append((item, "session_end" in handlers))
        elif "session_end has dedup declared" in item:
            se = handlers.get("session_end", {}) or {}
            results.append((item, "dedup" in se))
        elif "session_end has state_changes declared" in item:
            se = handlers.get("session_end", {}) or {}
            results.append((item, "state_changes" in se))
        elif "level_up rule states: AI proposes, student confirms" in item:
            # proxy: check in .scenarios.yml level_up scenario
            lu = rs.get("level_up", {}) if isinstance(rs, dict) else {}
            lu_str = yaml.dump(lu)
            passed = ("AI proposes" in sc_content or "proposes" in lu_str) and \
                     ("student confirms" in sc_content or "confirms" in lu_str)
            results.append((item, passed))
        else:
            results.append((item, None))

    return results


def check_gakusei_yml(repo: Path, items: list) -> list:
    gakusei_path = repo / ".gakusei.yml"
    if not gakusei_path.exists():
        return [(item, None) for item in items]
    try:
        parsed = yaml.safe_load(gakusei_path.read_text()) or {}
    except yaml.YAMLError:
        parsed = {}

    valid_levels = {"not_started", "beginner", "intermediate", "advanced"}
    results = []
    for item in items:
        if "name field exists" in item:
            results.append((item, "name" in parsed))
        elif "language field exists" in item:
            results.append((item, "language" in parsed))
        elif "subjects field exists as map" in item:
            results.append((item, isinstance(parsed.get("subjects"), dict)))
        elif "levels are one of" in item:
            subjects = parsed.get("subjects", {})
            if isinstance(subjects, dict):
                bad = [v for v in subjects.values() if v not in valid_levels]
                if bad:
                    print(f"    invalid levels: {bad}")
                results.append((item, len(bad) == 0))
            else:
                results.append((item, None))
        elif "last_session field exists" in item:
            ls = parsed.get("last_session", {})
            passed = isinstance(ls, dict) and all(k in ls for k in ["subject", "topic", "next"])
            results.append((item, passed))
        elif "active_books field exists" in item:
            results.append((item, "active_books" in parsed))
        elif "completed_books field exists" in item:
            results.append((item, "completed_books" in parsed))
        elif "exams field exists" in item:
            exams = parsed.get("exams", {})
            if isinstance(exams, dict) and exams:
                first = next(iter(exams.values()), {})
                passed_ok = isinstance(first, dict) and "passed" in first and "score" in first
                results.append((item, passed_ok))
            else:
                results.append((item, None))
        else:
            results.append((item, None))
    return results


def check_behaviour(repo: Path, items: list) -> list:
    content, parsed = _load_agent(repo)
    sc_content, sc_parsed = _load_scenarios(repo)
    rs = sc_parsed.get("required_scenarios", {}) if isinstance(sc_parsed, dict) else {}

    results = []
    for item in items:
        if "AI reads .gakusei.yml at every session start" in item:
            passed = ".gakusei.yml" in content and "session_start" in content
            results.append((item, passed, "proxy: .gakusei.yml in file_access + session_start scenario"))

        elif "gakusei.md does not need to pre-exist" in item:
            results.append((item, True, "structural rule — always true by convention"))

        elif "kiroku files are append-only" in item:
            fa = parsed.get("file_access", {}) or {}
            kiroku_val = str(fa.get("kiroku/**", fa.get("kiroku/", ""))).lower()
            passed = "append" in kiroku_val
            results.append((item, passed, "proxy: file_access.kiroku/** is append-only"))

        elif "shinsa records are committed before the AI responds" in item:
            passed = "commit before responding" in content
            results.append((item, passed, "proxy: write_ahead.rule declares commit-before-respond"))

        elif "shinsa gives no feedback during the exam" in item:
            passed = "no feedback" in sc_content or "only final score" in sc_content or "only your final score" in sc_content
            results.append((item, passed, "proxy: shinsa scenario describes no-feedback rule"))

        elif "shinsa has exactly 10 open-ended questions" in item:
            count = sc_content.count("open_exam_question_")
            passed = count == 10
            if not passed:
                print(f"    found {count} open_exam_question_ tokens, expected 10")
            results.append((item, passed, f"proxy: {count} open_exam_question_ tokens in .scenarios.yml"))

        elif "quiz uses multiple choice" in item:
            passed = "A, B, C or D" in sc_content or "mc_question" in sc_content
            results.append((item, passed, "proxy: quiz scenario uses mc_question tokens"))

        elif "level_up requires student confirmation" in item:
            lu = rs.get("level_up", {}) if isinstance(rs, dict) else {}
            lu_str = yaml.dump(lu)
            passed = ("AI proposes" in sc_content or "proposes" in lu_str) and \
                     ("student confirms" in sc_content or "confirms" in lu_str)
            results.append((item, passed, "proxy: level_up scenario in .scenarios.yml declares propose+confirm"))

        elif "templates are read before generating" in item:
            passed = "templates" in content and "read" in content
            results.append((item, passed, "proxy: templates declared in file_access and write_ahead"))

        else:
            results.append((item, None, ""))

    return results


def _print_result(item: str, result, note: str = ""):
    if result is True:
        suffix = f" — {note}" if note else ""
        print(f"  \u2705 {item}{suffix}")
    elif result is False:
        print(f"  \u274c {item}")
    else:
        print(f"  \u26a0\ufe0f  {item} (manual check required)")


def run(framework: str, repo_path: str):
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        print(f"[giskard] ERROR: repo path not found: {repo}")
        sys.exit(1)

    print(f"[giskard] validating '{repo.name}' as framework: {framework}")
    print(f"[giskard] loading checklist from zeroth...")
    checklist = load_checklist(framework)

    passed = 0
    failed = 0
    skipped = 0

    def count(result):
        nonlocal passed, failed, skipped
        if result is True: passed += 1
        elif result is False: failed += 1
        else: skipped += 1

    for section, items in checklist.items():
        print(f"\n\u2502 {section}")

        if section == "structure":
            for item, result in check_structure(repo, items, framework):
                _print_result(item, result)
                count(result)

        elif section == "agent_yml":
            if isinstance(items, dict):
                for item, result in check_agent_yml(repo, items):
                    _print_result(item, result)
                    count(result)
            else:
                for item in items:
                    _print_result(item, None)
                    skipped += 1

        elif section == "gakusei_yml":
            for item, result in check_gakusei_yml(repo, items):
                _print_result(item, result)
                count(result)

        elif section == "behaviour":
            for item, result, note in check_behaviour(repo, items):
                _print_result(item, result, note)
                count(result)

        elif section == "strict_root":
            for item, result in check_strict_root(repo, items):
                _print_result(item, result)
                count(result)

        elif section == "dynamic_dirs":
            for item, result in check_dynamic_dirs(repo, items):
                _print_result(item, result)
                count(result)

        else:
            if isinstance(items, list):
                for item in items:
                    print(f"  \u26a0\ufe0f  {item} (manual check required)")
                    skipped += 1
            else:
                print(f"  \u26a0\ufe0f  {section} (manual check required)")
                skipped += 1

    print(f"\n[giskard] result: {passed} passed / {failed} failed / {skipped} skipped")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — Malstrom framework validator")
    parser.add_argument("--framework", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    run(args.framework, args.repo)
