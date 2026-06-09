#!/usr/bin/env python3
"""
giskard — framework validator for the Malstrom ecosystem
Reads zeroth checklists and validates a repo against them.

Usage:
  python giskard.py --framework dojo --repo /path/to/repo
"""

import argparse
import os
import sys
import yaml
from pathlib import Path

ZEROTH_CHECKLISTS = {
    "dojo": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/dojo/checklist.yml",
    "tensho": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/tensho/checklist.yml",
    "sudo-hire-me": "https://raw.githubusercontent.com/Malstrom/zeroth/main/frameworks/sudo-hire-me/checklist.yml",
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


def check_structure(repo: Path, items: list) -> list[tuple[str, bool]]:
    results = []
    for item in items:
        # parse simple existence checks from checklist strings
        if "exists in root" in item:
            filename = item.split(" exists in root")[0].strip()
            exists = (repo / filename).exists()
            results.append((item, exists))
        elif "exists with" in item:
            dirname = item.split(" exists with")[0].strip()
            exists = (repo / dirname).is_dir()
            results.append((item, exists))
        elif "directory exists" in item:
            dirname = item.split(" directory exists")[0].strip()
            exists = (repo / dirname).is_dir()
            results.append((item, exists))
        else:
            # unrecognised check format — skip with warning
            results.append((item, None))
    return results


def check_agent_yml(repo: Path, items: list) -> list[tuple[str, bool]]:
    agent_path = repo / ".agent.yml"
    if not agent_path.exists():
        return [(item, False) for item in items]

    with open(agent_path) as f:
        content = f.read()

    results = []
    for item in items:
        if "connector_check is the first block" in item:
            # first non-comment non-empty line should be connector_check
            lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
            passed = lines[0].strip().startswith("connector_check") if lines else False
            results.append((item, passed))
        elif "destructive_ops is true" in item:
            passed = "destructive_ops: true" in content
            results.append((item, passed))
        elif "pr_strategy is batch_per_session" in item:
            passed = "pr_strategy: batch_per_session" in content
            results.append((item, passed))
        else:
            # generic keyword presence check
            keyword = item.split(" ")[0]
            results.append((item, keyword.lower() in content.lower()))
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
            results = check_structure(repo, items)
        elif section == "agent_yml":
            results = check_agent_yml(repo, items)
        else:
            results = [(item, None) for item in items]

        for item, result in results:
            if result is True:
                print(f"  \u2705 {item}")
                passed += 1
            elif result is False:
                print(f"  \u274c {item}")
                failed += 1
            else:
                print(f"  \u26a0\ufe0f  {item} (manual check required)")
                skipped += 1

    print(f"\n[giskard] result: {passed} passed / {failed} failed / {skipped} skipped")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — Malstrom framework validator")
    parser.add_argument("--framework", required=True, help="framework name (e.g. dojo)")
    parser.add_argument("--repo", required=True, help="path to the repo to validate")
    args = parser.parse_args()
    run(args.framework, args.repo)
