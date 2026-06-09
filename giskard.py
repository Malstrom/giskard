#!/usr/bin/env python3
"""
giskard — framework validator for the Malstrom ecosystem
Reads zeroth checklists and validates a repo against them.

Usage:
  python giskard.py --framework dojo --repo /path/to/repo
"""

import argparse
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
        "scroll.md",
        "log_exam.md",
        "log_randori.md",
        "log_study.md",
        "randori.html",
    ]
}


def load_checklist(framework: str) -> dict:
    import urllib.request
    url = ZEROTH_CHECKLISTS.get(framework)
    if not url:
        print(f"[giskard] ERROR: unknown framework '{framework}'")
        print(f"[giskard] registered frameworks: {', '.join(ZEROTH_CHECKLISTS.keys())}")
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
                print(f"    missing: {', '.join(missing)}")
            results.append((item, len(missing) == 0))

        elif "exists with" in item:
            parts = item.split(" exists with ")
            dirname = parts[0].strip().rstrip("/")
            dir_path = repo / dirname
            if not dir_path.is_dir():
                results.append((item, False))
                continue
            required_files = [f.strip() for f in parts[1].replace(" and ", ",").split(",")]
            all_present = all((dir_path / f).exists() for f in required_files)
            results.append((item, all_present))

        elif "directory exists" in item:
            dirname = item.split(" directory exists")[0].strip().rstrip("/")
            results.append((item, (repo / dirname).is_dir()))

        else:
            results.append((item, None))

    return results


def check_agent_yml(repo: Path, items: list) -> list:
    agent_path = repo / ".agent.yml"
    if not agent_path.exists():
        return [(item, False) for item in items]

    with open(agent_path) as f:
        content = f.read()

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"    [giskard] WARN: .agent.yml parse error: {e}")
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    results = []
    for item in items:

        if "connector_check is the first block" in item:
            lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
            passed = lines[0].strip().startswith("connector_check") if lines else False
            results.append((item, passed))

        elif "global.language reads from sensei.md" in item:
            passed = "sensei.md" in content and "language" in content
            results.append((item, passed))

        elif "global.pr_strategy is batch_per_session" in item:
            passed = "batch_per_session" in content
            results.append((item, passed))

        elif "write_ahead.exam_mode is defined" in item:
            passed = "exam_mode" in content and "write_ahead" in content
            results.append((item, passed))

        elif "tool_approval.destructive_ops is true" in item:
            passed = "destructive_ops: true" in content
            results.append((item, passed))

        elif "all 6 required scenarios are present" in item:
            scenarios = parsed.get("scenarios", {})
            count = len(scenarios) if isinstance(scenarios, dict) else 0
            if count != 6:
                print(f"    found {count} scenarios, expected 6: {list(scenarios.keys()) if scenarios else []}")
            results.append((item, count >= 6))

        elif "all 3 required handlers are present" in item:
            handlers = parsed.get("handlers", {})
            count = len(handlers) if isinstance(handlers, dict) else 0
            if count != 3:
                print(f"    found {count} handlers, expected 3: {list(handlers.keys()) if handlers else []}")
            results.append((item, count >= 3))

        elif "template_rule mapping covers all required templates" in item:
            passed = "template_rule" in content and "templates/" in content
            results.append((item, passed))

        else:
            results.append((item, None))

    return results


def check_behaviour(repo: Path, items: list) -> list:
    """
    Option C: proxy checks.
    We cannot observe runtime behaviour, but we verify that the rules
    governing each behaviour are correctly declared in .agent.yml.
    A passing proxy check means the instruction is present — not that the AI follows it.
    """
    agent_path = repo / ".agent.yml"
    if not agent_path.exists():
        return [(item, None) for item in items]

    with open(agent_path) as f:
        content = f.read()

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    results = []
    for item in items:

        if "exam logs are committed before AI responds" in item:
            # proxy: write_ahead.rule = commit before responding
            passed = "commit before responding" in content and "write_ahead" in content
            results.append((item, passed, "proxy: write_ahead.rule declares commit-before-respond"))

        elif "exam logs are never overwritten" in item:
            # proxy: write_ahead.exam_mode.on_self_correction = append, never overwrite
            passed = "never overwrite" in content and "append" in content
            results.append((item, passed, "proxy: write_ahead.exam_mode declares append-only"))

        elif "AI language is read from sensei.md not hardcoded" in item:
            # proxy: global.language = read from sensei.md (not a literal language name)
            gl = parsed.get("global", {}) or {}
            lang_val = str(gl.get("language", ""))
            passed = "sensei.md" in lang_val
            results.append((item, passed, "proxy: global.language references sensei.md not hardcoded value"))

        elif "AI does not read README.md" in item:
            # proxy: file_access declares readme_files as write-only or not readable
            fa = parsed.get("file_access", {}) or {}
            readme_access = str(fa.get("readme_files", "")).lower()
            passed = readme_access in ("write-only", "none")
            results.append((item, passed, "proxy: file_access.readme_files is write-only"))

        elif "templates are read before generating" in item:
            # proxy: template_rule.rule declares read-before-generate
            tr = parsed.get("template_rule", {}) or {}
            rule_val = str(tr.get("rule", "")).lower()
            passed = "read" in rule_val and "template" in rule_val
            results.append((item, passed, "proxy: template_rule.rule declares read-before-generate"))

        else:
            results.append((item, None, ""))

    return results


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

    for section, items in checklist.items():
        print(f"\n\u2502 {section}")

        if section == "structure":
            results = check_structure(repo, items, framework)
            for item, result in results:
                _print_result(item, result, "")
                _count(result, locals())
                if result is True: passed += 1
                elif result is False: failed += 1
                else: skipped += 1

        elif section == "agent_yml":
            results = check_agent_yml(repo, items)
            for item, result in results:
                _print_result(item, result, "")
                if result is True: passed += 1
                elif result is False: failed += 1
                else: skipped += 1

        elif section == "behaviour":
            results = check_behaviour(repo, items)
            for item, result, note in results:
                _print_result(item, result, note)
                if result is True: passed += 1
                elif result is False: failed += 1
                else: skipped += 1

        else:
            for item in items:
                print(f"  \u26a0\ufe0f  {item} (manual check required)")
                skipped += 1

    print(f"\n[giskard] result: {passed} passed / {failed} failed / {skipped} skipped")
    if failed > 0:
        sys.exit(1)


def _print_result(item: str, result, note: str):
    if result is True:
        suffix = f" — {note}" if note else ""
        print(f"  \u2705 {item}{suffix}")
    elif result is False:
        print(f"  \u274c {item}")
    else:
        print(f"  \u26a0\ufe0f  {item} (manual check required)")


def _count(result, scope):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — Malstrom framework validator")
    parser.add_argument("--framework", required=True, help="framework name (e.g. dojo)")
    parser.add_argument("--repo", required=True, help="path to the repo to validate")
    args = parser.parse_args()
    run(args.framework, args.repo)
