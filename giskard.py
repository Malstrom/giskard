#!/usr/bin/env python3
"""
giskard — universal zeroth rules validator.

Two modes:

  instance (default)
    Validates a student/user instance repo against zeroth universal rules
    and optional framework-specific instance checks.

    python giskard.py --repo /path/to/instance --framework dojo

  zeroth
    Validates the zeroth repo itself — checks that framework spec files
    (scenarios, templates, structure) are well-formed.

    Autodiscover all frameworks:
      python giskard.py --repo /path/to/zeroth --mode zeroth

    Single framework (dev/targeted):
      python giskard.py --repo /path/to/zeroth --mode zeroth --framework dojo

Exit codes:
  0  all checks passed
  1  one or more checks FAILED
  2  internal validator error

Adding a framework:
  instance checks: checks/frameworks/{name}.py  with run(repo, report)
  zeroth checks:   checks/zeroth/{name}.py       with run(repo, report)
  See checks/frameworks/README.yml for the full contract.
"""

import argparse
import importlib
import sys
from pathlib import Path

from core import Report, ERROR, _gh_annotation
from checks import universal


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


def load_module(package: str, name: str):
    try:
        return importlib.import_module(f"{package}.{name}")
    except ModuleNotFoundError:
        return None


def discover_frameworks(repo: Path) -> list[str]:
    """Return sorted list of framework names found in repo/frameworks/."""
    frameworks_dir = repo / "frameworks"
    if not frameworks_dir.is_dir():
        return []
    return sorted(d.name for d in frameworks_dir.iterdir() if d.is_dir())


def run(repo_path: str, framework: str = None, mode: str = "instance", github_token: str = None):
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        print(f"[giskard] ERROR: repo path not found: {repo}")
        sys.exit(2)

    print(f"[giskard] validating '{repo.name}' (mode: {mode})")

    report = Report(repo)

    if mode == "zeroth":
        # zeroth mode: validate spec files inside a zeroth clone.
        # Universal rules are skipped — zeroth is not an instance.
        if framework:
            frameworks = [framework]
        else:
            frameworks = discover_frameworks(repo)
            if not frameworks:
                print("[giskard] WARNING: no frameworks found in repo/frameworks/ — nothing to check")
            else:
                print(f"[giskard] discovered frameworks: {', '.join(frameworks)}")

        for fw_name in frameworks:
            fw = load_module("checks.zeroth", fw_name)
            if fw is None:
                msg = (
                    f"zeroth checks for framework '{fw_name}' not yet implemented. "
                    f"Add checks/zeroth/{fw_name}.py to enable."
                )
                print(f"\n[giskard] WARNING: {msg}")
                _gh_annotation("warning", f"giskard: {msg}")
            else:
                fw.run(repo, report)

    else:
        # instance mode (default): universal rules + optional framework checks.
        universal.run(repo, report)

        if framework:
            fw = load_module("checks.frameworks", framework)
            if fw is None:
                msg = (
                    f"framework '{framework}' not yet supported — skipping framework-specific checks. "
                    f"Add checks/frameworks/{framework}.py to enable. "
                    f"See checks/frameworks/README.yml for the contract."
                )
                print(f"\n[giskard] WARNING: {msg}")
                _gh_annotation("warning", f"giskard: {msg}")
            else:
                fw.run(repo, report)

    print(f"\n[giskard] result: {report.passed} passed / {report.failed} failed / "
          f"{report.skipped} skipped / {report.errored} errored")

    report_path = report.save()

    print("\n" + "=" * 60)
    print(report_path.read_text())
    print("=" * 60)

    if not report.ok and github_token:
        open_failure_issue(report, repo.name, github_token)

    if report.errored > 0:
        sys.exit(2)
    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="giskard — zeroth rules validator")
    parser.add_argument("--repo", required=True, help="Path to repo to validate")
    parser.add_argument("--framework", default=None, help="Framework-specific checks (dojo, aurora, ...). In zeroth mode, omit to autodiscover all frameworks.")
    parser.add_argument("--mode", default="instance", choices=["instance", "zeroth"],
                        help="Validation mode: 'instance' (default) or 'zeroth'")
    parser.add_argument("--github-token", default=None, dest="github_token",
                        help="GitHub token for opening issues on failure")
    args = parser.parse_args()
    run(args.repo, args.framework, args.mode, args.github_token)
