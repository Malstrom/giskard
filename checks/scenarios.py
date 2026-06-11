"""
checks/scenarios.py — rules/scenarios.yml

Validates .scenarios.yml structure (universal checks) and tracks scenario
changes via snapshots stored in giskard state/ directory.

Snapshot tracking (phase 2 of giskard#33):
  On every run, compares current .scenarios.yml against the last known
  snapshot in state/{repo_name}/.scenarios.snapshot.yml.
  If scenarios were added, removed, or modified:
    - Opens an issue in giskard repo titled 'scenario coverage review needed: {repo}'
    - Updates the snapshot to current state
  Requires --github-token to open issues and write snapshot back.
  Skipped silently if token not available.
"""

import json
import os
import urllib.request
import urllib.error
import yaml
from pathlib import Path
from core import run_check, Report, _gh_annotation

CHECKS = [
    {
        "label": ".scenarios.yml root key is required_scenarios",
        "proxy": "yaml_first_key",
        "file": ".scenarios.yml",
        "expected": "required_scenarios",
        "rule": "scenarios.yml",
    },
    {
        "label": "session_start scenario present",
        "proxy": "scenario_present",
        "scenario": "session_start",
        "rule": "scenarios.yml",
    },
    {
        "label": "unknown_scenario present",
        "proxy": "scenario_present",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    {
        "label": "unknown_scenario is last",
        "proxy": "scenario_last",
        "scenario": "unknown_scenario",
        "rule": "scenarios.yml",
    },
    {
        "label": "handlers do not use say/ask/propose",
        "proxy": "scenario_no_forbidden_modules",
        "file": ".agent.yml",
        "rule": "scenarios.yml",
    },
]


def _parse_scenarios(content: str) -> dict:
    """Return {name: hash_of_content} for all scenarios."""
    try:
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            rs = parsed.get("required_scenarios") or {}
            if isinstance(rs, dict):
                return {
                    name: str(body) for name, body in rs.items()
                }
    except Exception:
        pass
    return {}


def _open_coverage_issue(repo_name: str, token: str,
                         added: list, removed: list, modified: list) -> None:
    parts = []
    if added:
        parts.append("**Added:** " + ", ".join(f"`{s}`" for s in added))
    if removed:
        parts.append("**Removed:** " + ", ".join(f"`{s}`" for s in removed))
    if modified:
        parts.append("**Modified:** " + ", ".join(f"`{s}`" for s in modified))

    body = (
        f"## Scenario coverage review needed: `{repo_name}`\n\n"
        f"Scenarios changed in `{repo_name}/.scenarios.yml`:\n\n"
        + "\n".join(parts)
        + "\n\n"
        f"**Action required:**\n"
        f"1. Review `checks/frameworks/{{framework}}.py` in giskard\n"
        f"2. Check the **Known gaps** section in the framework spec\n"
        f"3. Add missing checks if needed\n"
        f"4. Close this issue when coverage is confirmed\n\n"
        f"---\n_Opened automatically by giskard scenario snapshot tracking._"
    )

    payload = json.dumps({
        "title": f"scenario coverage review needed: {repo_name}",
        "body": body,
        "labels": ["scenario-coverage"],
    }).encode()

    url = "https://api.github.com/repos/Malstrom/giskard/issues"
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
            print(f"[giskard] scenario coverage issue opened: {data['html_url']}")
    except urllib.error.HTTPError as e:
        print(f"[giskard] WARNING: could not open coverage issue: {e.code} {e.reason}")


def _update_snapshot(repo: Path, snapshot_path: Path,
                     current_content: str, token: str) -> None:
    """
    Write updated snapshot back to giskard repo via GitHub API.
    snapshot_path is relative to giskard repo root.
    """
    import base64

    rel = str(snapshot_path)
    url = f"https://api.github.com/repos/Malstrom/giskard/contents/{rel}"

    # get current SHA if file exists
    sha = None
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            sha = data.get("sha")
    except Exception:
        pass

    payload_data = {
        "message": f"chore: update scenario snapshot for {repo.name}",
        "content": base64.b64encode(current_content.encode()).decode(),
    }
    if sha:
        payload_data["sha"] = sha

    payload = json.dumps(payload_data).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"[giskard] snapshot updated: {rel}")
    except urllib.error.HTTPError as e:
        print(f"[giskard] WARNING: could not update snapshot: {e.code} {e.reason}")


def _check_scenario_snapshot(repo: Path, report: Report) -> None:
    token = os.environ.get("GISKARD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return  # no token — skip silently

    scenarios_file = repo / ".scenarios.yml"
    if not scenarios_file.exists():
        return

    current_content = scenarios_file.read_text(encoding="utf-8")
    current = _parse_scenarios(current_content)

    # snapshot lives in giskard repo (checked out at _giskard/ by action)
    # but when running locally it's relative to giskard.py location
    giskard_root = Path(__file__).parent.parent  # checks/ -> giskard root
    snapshot_rel = Path(f"state/{repo.name}/.scenarios.snapshot.yml")
    snapshot_path = giskard_root / snapshot_rel

    if snapshot_path.exists():
        prev = _parse_scenarios(snapshot_path.read_text(encoding="utf-8"))
    else:
        prev = {}

    added = sorted(set(current) - set(prev))
    removed = sorted(set(prev) - set(current))
    modified = sorted(
        name for name in set(current) & set(prev)
        if current[name] != prev[name]
    )

    if not (added or removed or modified):
        report.add("scenario snapshot: no changes detected", True)
        return

    # emit warning
    summary_parts = []
    if added:
        summary_parts.append(f"added: {', '.join(added)}")
    if removed:
        summary_parts.append(f"removed: {', '.join(removed)}")
    if modified:
        summary_parts.append(f"modified: {', '.join(modified)}")
    summary = " — ".join(summary_parts)

    print(f"\n[giskard] ⚠️  scenario changes in {repo.name}: {summary}")
    _gh_annotation("warning", f"giskard: scenario coverage review needed — {summary}", ".scenarios.yml")
    report.add(f"scenario snapshot: changes detected — coverage review needed", None, summary)

    # open issue in giskard
    _open_coverage_issue(repo.name, token, added, removed, modified)

    # update snapshot
    _update_snapshot(repo, snapshot_rel, current_content, token)


def run(repo: Path, report: Report) -> None:
    report.section("scenarios")
    for check in CHECKS:
        run_check(repo, check, report)
    _check_scenario_snapshot(repo, report)
