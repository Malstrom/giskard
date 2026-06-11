#!/usr/bin/env python3
"""
giskard — universal zeroth rules validator.

Runs rules-based checks on any repo in the Malstrom ecosystem.
Optionally runs framework-specific checks if --framework is passed.

Usage:
  python giskard.py --repo /path/to/repo
  python giskard.py --repo /path/to/repo --framework dojo
  python giskard.py --repo /path/to/repo --github-token TOKEN

Exit codes:
  0  all checks passed (framework-specific checks may be skipped with a warning)
  1  one or more checks FAILED
  2  internal validator error
"""

import argparse
import importlib
import sys
from pathlib import Path

from core import Report, ERROR, _gh_annotation
from checks import files, agent, scenarios, connections


def open_failure_issue(report: Report, repo_name: str, token: str):
    """Open a giskard-violation issue in the target repo on GitHub."""
    import urllib.request
    import urllib.error
    import json

    if not report.failures:
        return

    lines = []
    for f in report.failures:
        line = f"- **{f['label']}**"
        if f["file"]:
            line += f" — `{f['file']}`"
        if f["rule"]:
            line += f" — rule: [{f['rule']}](https://github.com/Malstrom/zeroth/blob/main/rules/{f['rule']})"
        lines.append(line)

    body = (
        "## giskard violation report\n\n"
        f"**date**: {report.ts}\n\n"
        "## failed checks\n\n"
        + "\n".join(lines)
        + "\n\n---\n"
        "_Cite this issue in a Perplexity chat to trigger the fix scenario._"
    )

    payload = json.dumps({
        "title": "giskard: validation failed",
        "body": body,
        "labels": ["giskard-violation"],
    }).encode()

    url = f"https://api.github.com/repos/Malstrom/{repo_name}/issues"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            print(f"[giskard] issue opened: {data['html_url']}")
    except urllib.error.HTTPError as e:
        print(f"[giskard] WARNING: could not open issue: {e.code} {e.reason}")


def load_framework_module(name: str):
    try:
        return importlib.import_module(f"checks.frameworks.{name}")
    except ModuleNotFoundError:
        return None


def run(repo_path: str, framework: str = None, github_token: str = None):
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        print(f"[giskard] ERROR: repo path not found: {repo}")
        sys.exit(2)

    print(f"[giskard] validating '{repo.name}'")
    if framework:
        print(f"[giskard] framework: {framework}")

    report = Report(repo)

    # Layer 1 — universal rules (always)
    files.run(repo, report)
    agent.run(repo, report)
    scenarios.run(repo, report)
    connections.run(repo, report)

    # Layer 2 — framework-specific (optional)
    if framework:
        fw = load_framework_module(framework)
        if fw is None:
            msg = f"framework '{framework}' not yet supported — skipping framework-specific checks. Add checks/frameworks/{framework}.py to enable."
            print(f"\n[giskard] WARNING: {msg}")
            _gh_annotation("warning", f"giskard: {msg}")
        else:
            fw.run(repo, report)

    print(f"\n[giskard] result: {report.passed} passed / {report.failed} failed / "
          f"{report.skipped} skipped / {report.errored} errored")

    # Always save report before exiting
    report_path = report.save()

    # Print report inline for CI log visibility
    print("\n" + "=" * 60)
    print(report_path.read_text())
    print("=" * 60)

    if not report.ok and github_token:
        open_failure_issue(report, repo.name, github_token)

    if report.errored > 0:
        sys.exit(2)
    if report.failed > 0:
        sys.exit(1)
    # exit 0 — framework warning does not fail the build


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — zeroth rules validator")
    parser.add_argument("--repo", required=True, help="Path to repo to validate")
    parser.add_argument("--framework", default=None, help="Optional framework-specific checks")
    parser.add_argument("--github-token", default=None, dest="github_token",
                        help="GitHub token for opening issues on failure")
    args = parser.parse_args()
    run(args.repo, args.framework, args.github_token)
